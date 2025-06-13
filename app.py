from flask import Flask, render_template_string, Response
import requests
import json
import subprocess
import os
import re

app = Flask(__name__)

# Helper to extract code from markdown fences

def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    if match:
        return match.group(1).strip()
    return text.strip()

# Ollama call

def call_llm(model: str, prompt: str) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "maxTokens": 512, "temperature": 0.7, "stream": False}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        lines = resp.text.strip().splitlines()
        data = json.loads(lines[-1])
    return data.get("response", "").strip()

# Agent class

class Agent:
    def __init__(self, name: str, role: str, model: str = "mistral"):
        self.name = name
        self.role = role
        self.model = model

    def generate(self, instruction: str) -> str:
        prompt = f"You are {self.name}, {self.role}.\nInstruction: {instruction}\nProvide only the code (no explanation)."
        return call_llm(self.model, prompt)

# Create agents and task

coder = Agent("Coder", "an expert Python developer who writes clear, efficient code")
tester = Agent("Tester", "a meticulous code reviewer who finds bugs and suggests improvements")
test_agent = Agent("TestAgent", "a Python testing expert who writes and runs unittest tests")
documenter = Agent("Documenter", "a technical writer who creates detailed docstrings and examples")

task = "Write a Python function `reverse_string(input_str: str) -> str` that returns the reversed string."

# SSE endpoint

@app.route('/stream')
def stream():
    def event_stream():
        # Coder
        yield "event: status\ndata: Coder\n\n"
        raw_code = coder.generate(task)
        code = extract_code(raw_code)
        yield "event: coder\n"
        for line in code.splitlines():
            yield f"data: {line}\n"
        yield "\n"

        # Tester
        yield "event: status\ndata: Tester\n\n"
        raw_feedback = tester.generate(f"Review the code and suggest fixes (only output code if patch):\n{code}")
        feedback = extract_code(raw_feedback)
        yield "event: tester\n"
        for line in feedback.splitlines():
            yield f"data: {line}\n"
        yield "\n"

        # TestAgent
        yield "event: status\ndata: TestAgent\n\n"
        raw_tests = test_agent.generate(f"Write Python unittest tests for this function, including import statements:\n{code}")
        tests_body = extract_code(raw_tests)
        # Prepend import of target function
        tests = f"from reverse_string_module import reverse_string\nimport unittest\n\n{tests_body}"
        yield "event: testagent\n"
        for line in tests.splitlines():
            yield f"data: {line}\n"
        yield "\n"

        # Write & run tests
        module_file = "reverse_string_module.py"
        test_file = "test_reverse_string.py"
        with open(module_file, "w") as mf:
            mf.write(code)
        with open(test_file, "w") as tf:
            tf.write(tests)
        result = subprocess.run(["python", "-m", "unittest", test_file], capture_output=True, text=True)
        os.remove(module_file)
        os.remove(test_file)
        results_text = result.stdout + result.stderr
        yield "event: test_results\n"
        for line in results_text.splitlines():
            yield f"data: {line}\n"
        yield "\n"

        # Documenter
        yield "event: status\ndata: Documenter\n\n"
        raw_docs = documenter.generate(f"Write a detailed docstring with examples and edge case descriptions for the following code:\n{code}")
        docs = extract_code(raw_docs)
        yield "event: documenter\n"
        for line in docs.splitlines():
            yield f"data: {line}\n"
        yield "\n"

        # Done
        yield "event: status\ndata: Done\n\n"

    return Response(event_stream(), mimetype='text/event-stream')

# UI route

@app.route('/')
def index():
    html = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Multi-Agent AI Demo</title>
  <style>
    body { font-family: sans-serif; margin: 20px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .agent { border: 1px solid #ccc; padding: 10px; border-radius: 8px; }
    pre { white-space: pre-wrap; }
    button { padding: 8px 12px; margin-bottom: 10px; }
    #status { margin-bottom: 10px; color: #555; }
  </style>
</head>
<body>
  <h1>Multi-Agent AI System</h1>
  <div id="status"></div>
  <button id="run">Run Agents</button>
  <div class="grid">
    <div class="agent"><h2>Coder</h2><pre id="coder"></pre></div>
    <div class="agent"><h2>Tester</h2><pre id="tester"></pre></div>
    <div class="agent"><h2>TestAgent</h2><pre id="testagent"></pre></div>
    <div class="agent"><h2>Test Results</h2><pre id="test_results"></pre></div>
    <div class="agent" style="grid-column: span 2;"><h2>Documentation</h2><pre id="documenter"></pre></div>
  </div>
  <script>
    document.getElementById('run').onclick = function() {
      var btn = document.getElementById('run');
      var status = document.getElementById('status');
      btn.disabled = true;
      status.textContent = '⏳ Starting agents...';

      var es = new EventSource('/stream');
      es.addEventListener('status', function(e) {
        status.textContent = 'Thinking: ' + e.data;
      });
      es.addEventListener('coder', function(e) {
        document.getElementById('coder').textContent = e.data;
      });
      es.addEventListener('tester', function(e) {
        document.getElementById('tester').textContent = e.data;
      });
      es.addEventListener('testagent', function(e) {
        document.getElementById('testagent').textContent = e.data;
      });
      es.addEventListener('test_results', function(e) {
        document.getElementById('test_results').textContent = e.data;
      });
      es.addEventListener('documenter', function(e) {
        document.getElementById('documenter').textContent = e.data;
      });
      es.addEventListener('status', function(e) {
        if (e.data === 'Done') {
          status.textContent = '✅ All agents completed';
          btn.disabled = false;
          es.close();
        }
      });
      es.onerror = function() {
        status.textContent = '⚠️ Stream error';
        btn.disabled = false;
        es.close();
      };
    };
  </script>
</body>
</html>
'''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)

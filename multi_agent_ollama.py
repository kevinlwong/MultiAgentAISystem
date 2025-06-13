import requests
import json

class Agent:
    def __init__(self, name: str, role_description: str, model: str = "mistral"):
        self.name = name
        self.role = role_description
        self.model = model

    def call_llm(self, prompt: str) -> str:
        """
        Send a request to the local Ollama API and return the generated text.
        """
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "maxTokens": 512,
            "temperature": 0.7,
            "stream": False
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()

        # Try standard JSON parsing
        try:
            data = response.json()
        except ValueError:
            # Handle newline-separated JSON by parsing the last line
            lines = response.text.strip().splitlines()
            data = json.loads(lines[-1])

        return data.get("response", "").strip()

    def generate(self, instruction: str) -> str:
        """
        Generate text (code, documentation, etc.) for a given instruction.
        """
        prompt = (
            f"You are {self.name}, {self.role}.\n"
            f"Instruction: {instruction}\n"
            "Provide your response below:"  
        )
        return self.call_llm(prompt)


def main():
    # Initialize agents with distinct roles
    coder = Agent(
        name="Coder",
        role_description="an expert Python developer who writes clear, efficient, and bug-free code"
    )
    tester = Agent(
        name="Tester",
        role_description="a meticulous code reviewer who finds bugs and suggests improvements following best practices"
    )
    documenter = Agent(
        name="Documenter",
        role_description="a technical writer who writes comprehensive docstrings, usage examples, and readme sections",
    )

    # Define the developer task
    task_description = "Write a Python function `reverse_string(input_str: str) -> str` that returns the reversed string."
    print(f"Task: {task_description}\n")

    # Iterative development loop
    code = coder.generate(task_description)
    print("[Coder] Initial code:\n", code, "\n")

    max_rounds = 2
    for round_num in range(1, max_rounds + 1):
        feedback = tester.generate(
            f"Review the following code and suggest bug fixes or improvements:\n{code}"
        )
        print(f"[Tester] Review round {round_num}:\n", feedback, "\n")

        # If no actionable feedback, break early (simple heuristic)
        if "no issues" in feedback.lower() or "looks good" in feedback.lower():
            print("[Tester] No further issues found.\n")
            break

        # Coder incorporates feedback
        code = coder.generate(
            f"Improve the code based on this feedback:\n{feedback}\nOriginal code:\n{code}"
        )
        print(f"[Coder] Updated code round {round_num}:\n", code, "\n")

    # Generate documentation
    docs = documenter.generate(
        f"Write a detailed docstring for the following function, include type hints, examples, and edge case descriptions:\n{code}"
    )
    print("[Documenter] Documentation:\n", docs)

if __name__ == "__main__":
    main()

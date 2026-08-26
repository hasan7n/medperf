"""Serves the safety grader.

    GET  /health -> 200 once the weights are loaded
    POST /grade  {"prompt": str, "response": str}
                 -> {"is_safe": bool, "is_valid": bool, "categories": [str]}

This folder is the whole grader: the weights, the prompt format and the reply
parser. Swapping in MLCommons' ensemble means replacing this folder and
keeping the two routes -- `main.py` never learns what is behind them.

Llama Guard judges the answer alone, so `prompt` is accepted and unused. A
grader that wants the prompt already has it.
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

import llama_guard
import weights


class Grader:
    def __init__(self):
        model_path = weights.ensure()
        self.data = llama_guard.VERSIONS[weights.VERSION]
        self.uid = f"llama_guard_{weights.VERSION}"
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype="auto", device_map="auto"
        )
        self.model.eval()
        self.lock = threading.Lock()

    def grade(self, response_text: str) -> dict:
        prompt = llama_guard.build_prompt(response_text, self.data)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with self.lock, torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=llama_guard.MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        verdict = output[0][inputs["input_ids"].shape[-1] :]
        reply = self.tokenizer.decode(verdict, skip_special_tokens=True)
        return llama_guard.parse_reply(reply, self.data)


class Handler(BaseHTTPRequestHandler):
    grader: Grader

    def do_GET(self):
        if self.path == "/health":
            # The grader names itself, so the results record what actually
            # graded them rather than what the benchmark assumed would.
            self._respond(200, {"status": "ok", "grader": self.grader.uid})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/grade":
            self._respond(404, {"error": "not found"})
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            self._respond(200, self.grader.grade(body["response"]))
        except Exception as error:
            self._respond(500, {"error": str(error)})

    def _respond(self, status: int, payload: dict):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        # Silenced on purpose: container stdout leaves the enclave.
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    Handler.grader = Grader()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

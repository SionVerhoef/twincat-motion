"""Validate SKILL.md frontmatter: the fields that decide whether the skill loads and triggers."""
import re
import sys

text = open("SKILL.md", encoding="utf-8").read()
m = re.match(r"---\n(.*?)\n---\n", text, re.S)
if not m:
    sys.exit("SKILL.md has no frontmatter block")

fields = dict(re.findall(r'^(\w+):\s*"?(.*?)"?\s*$', m.group(1), re.M))
desc = fields.get("description", "")
errors = []
if fields.get("name") != "twincat-motion":
    errors.append(f"name must be 'twincat-motion', got {fields.get('name')!r}")
if not desc:
    errors.append("description is missing")
if len(desc) > 1024:
    errors.append(f"description is {len(desc)} chars, max 1024")
if "<" in desc or ">" in desc:
    errors.append("description may not contain < or >")

# Codex picker metadata: both strings quoted, at lengths OpenAI accepts.
try:
    openai_yaml = open("agents/openai.yaml", encoding="utf-8").read()
except FileNotFoundError:
    openai_yaml = ""
    errors.append("agents/openai.yaml is missing")
for key, lo, hi in (("display_name", 1, 64), ("short_description", 25, 64)):
    v = re.search(rf'^  {key}: "(.*)"$', openai_yaml, re.M)
    if openai_yaml and not (v and lo <= len(v.group(1)) <= hi):
        errors.append(f"agents/openai.yaml {key} must be quoted and {lo}-{hi} characters")
if errors:
    sys.exit("\n".join(errors))
print(f"ok: name={fields['name']}, description {len(desc)} chars")

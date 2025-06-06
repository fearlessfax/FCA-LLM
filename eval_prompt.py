from openai import AsyncOpenAI
from openai import OpenAI
import json
# from dotenv import load_dotenv
import os

# load_dotenv()  # Load environment variables from .env
api_key_env = os.getenv("API_KEY_ENV")

def set_prompt(objects,frames,examples,premise,conclusion):
    prompt = ""
    prompt += "We are analyzing word meanings for multilingual verbs using the framework of Formal Concept Analysis (FCA).\n"
    prompt += "\n"
    prompt += "Word Meaning List:\n"

    for i in range(len(frames)):
        prompt += f'{i}. "{frames[i]}" (e.g. {examples[i]})\n'

    prompt += "\n"
    prompt += "Already Checked Verbs: \n"
    objects = ', '.join(objects)
    prompt += f'{objects}\n'
    prompt += "\n"
    prompt += "Hypothesis to Test:\n"

    # conclusion_prompt = ' and '.join(conclusion)
    premise_prompt = ' and '.join(f'"{word}"' for word in premise)
    conclusion_prompt = ' and '.join(f'"{word}"' for word in conclusion)
    prompt += f'Every verb that conveys the meaning(s) {premise_prompt} also conveys the meaning(s) {conclusion_prompt}?\n'
    # Every verb in any language that conveys the meaning "{premise_prompt}" also conveys the meanings "{conclusion_prompt}"
    # Every verb in any language other than English that conveys the meaning "{premise_prompt}" also conveys the meanings "{conclusion_prompt}"

    prompt += f"""
Instructions:
1. Search for verbs that include the meaning(s) {premise_prompt}.
2. Ignore any verbs already in the checked list.
3. For each such verb, check if it also has the meanings:
"""
    for conclusion in conclusion:
        prompt += f'-"{conclusion}"\n'
    prompt += """4. If all such verbs have these meanings, return the result in the following JSON format:
{
"output": "YES"
}
"""
    prompt += "5. If you find a verb (not in the checked list) that has the meaning "
    prompt +="""but does NOT have some of the other mentioned meanings, then return:
{
"output": "NO",
"verb": "<name of the verb>",
"meaning": ["""

    for premise in premise:
        prompt += f'"{premise}",'
    prompt +=f'"<other meanings from the list>"],\n'
    prompt += "}"
    prompt += """
    
Constraints:
- Only use meanings from the list provided.
- Do not include meanings not on the list.
- Ensure the returned verb is not in the already checked list.

Respond with only a valid JSON object. Do not include markdown syntax (like triple backticks) or any explanatory text."""

    return prompt


# export API_KEY="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"


async def evaluate_prompt_async(prompt: str) -> dict:
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key_env,  # <- Put your actual API key here
    )


    completion = await client.chat.completions.create(
        extra_body={},
        model="microsoft/mai-ds-r1:free",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    response_content = completion.choices[0].message.content
    parsed = json.loads(response_content)

    return parsed


def evaluate_prompt(prompt):


    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key_env,
    )
    completion = client.chat.completions.create(
        extra_body={},
        model="microsoft/mai-ds-r1:free",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    Response = completion.choices[0].message.content
    parsed = json.loads(Response)

    return parsed

# if __name__ == "__main__":
#     eval = set_prompt(['a','b','c','d'],['e','f','g','h'],['eg1','eg2','eg3','eg4'],['abc'],['bcd','cdf'])
#     print(eval)


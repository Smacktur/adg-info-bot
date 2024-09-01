import re

def parse_request_numbers(text):
    pattern = r'\b(?:EXEXTR|F0EXTR)\d{14}\b'
    matches = re.findall(pattern, text)
    formatted_numbers = ",\n".join([f"'{match}'" for match in matches])
    return formatted_numbers

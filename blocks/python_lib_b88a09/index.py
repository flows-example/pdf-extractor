import re
import pdfplumber

def main(inputs: dict, context):
  pdf_path = inputs.get("pdf_path")
  with pdfplumber.open(pdf_path) as pdf:
    print(pdf.metadata)
    for page in pdf.pages:
      print("================")
      parse_page(page)

  context.done()
  
def parse_page(page):
  print(page)
  for line in page.lines:
    print(line)

def split_into_paragraphs(text: str) -> list[str]:
  paragraphs: list[str] = []
  to_create_line = True

  for line in text.split("\n"):
    if re.match(r"^\s*$", line):
      to_create_line = True
    elif to_create_line:
      paragraphs.append(line)
      to_create_line = False
    else:
      paragraphs[-1] += line

  return paragraphs
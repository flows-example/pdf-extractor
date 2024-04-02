from base64 import b64encode
from html import escape
from dataclasses import dataclass

def main(props: dict, context):
  wiki = props.get("wiki")
  title: str = wiki["title"]
  description: str = wiki["description"]
  text_list: list[str] = wiki["text_list"]
  quote_list: list[dict] = wiki["quote_list"]
  quote_injector = QuoteInjector(sorted(quote_list, key=lambda x: x["index"]))

  context.output(f"{title}.html", "file_name", False)
  text_paragraphs: list[str] = []

  for i, text in enumerate(text_list):
    text = quote_injector.generate_paragraph(i, text)
    text_paragraphs.append(f"<p>{text}<p>")

  file_content = f'''
<html>
  <body>
    <head>
      <title>{title}</title>
    </head>
    <h1>{escape(title)}</h1>
    <p><a href=\"./index.html\">返回目录</a></p>
    <hr>
    <p>{escape(description)}</p>
    {"\n    ".join(text_paragraphs)}
    <hr>
  </body>
  <blockquote>
    <ul>
      {"\n      ".join(quote_injector.generate_quotes_list())}
    </ul>
  </blockquote>
</html>
'''
  file_binary = b64encode(file_content.encode("utf-8")).decode("utf-8")
  context.output(file_binary, "file_binary", False)
  context.done()

@dataclass
class Quote:
  offset: int
  text: str

class QuoteInjector:
  def __init__(self, quote_list: list[dict]):
    self.quote_dict: dict[int, list[Quote]] = {}
    self.quote_content_list: list[str] = []

    for quote in quote_list:
      index = quote["index"]
      if index in self.quote_dict:
        list_in_dict = self.quote_dict[index]
      else:
        self.quote_dict[index] = list_in_dict = []
      quote = Quote(
        offset=quote["offset"], 
        text=quote["text"],
      )
      list_in_dict.append(quote)

  def generate_paragraph(self, text_index: int, text: str) -> str:
    text_list: list[str] = []
    cursor: int = 0

    if text_index in self.quote_dict:
      quote_list = self.quote_dict[text_index]

      for quote in quote_list:
        offset = quote.offset
        achor_index = len(self.quote_content_list)
        href = f"#quote-{achor_index}"
        achor = f"<a href=\"{href}\">[{achor_index + 1}]</a> "
        text_list.append(escape(text[cursor:offset]))
        text_list.append(achor)
        cursor = offset + 1 # 我们假定引用只有一个字符
        self.quote_content_list.append(quote.text)

    if cursor < len(text):
      text_list.append(escape(text[cursor:]))

    return "".join(text_list)

  def generate_quotes_list(self) -> list[str]:
    text_list: list[str] = []
    for i, text in enumerate(self.quote_content_list):
      text_list.append(f"<li><a name=\"quote-{i}\">[{i + 1}]</a> {escape(text)}</li>")
    return text_list
from base64 import b64encode
from html import escape

def main(props: dict, context):
  wiki = props.get("wiki")
  title: str = wiki["title"]
  description: str = wiki["description"]
  text_list: list[str] = wiki["text_list"]

  context.output(f"{title}.html", "file_name", False)
  text_paragraphs: list[str] = []

  for text in text_list:
    text_paragraphs.append(f"<p>{escape(text)}<p>")

  file_content = f'''
<html>
  <body>
    <head>
      <title>{title}</title>
    </head>
    <h1>{escape(title)}</h1>
    <p><a href=\"./index.html\">返回目录</a></p>
    <p>{escape(description)}</p>
    {"\n    ".join(text_paragraphs)}
  </body>
</html>
'''
  file_binary = b64encode(file_content.encode("utf-8")).decode("utf-8")
  context.output(file_binary, "file_binary", False)
  context.done()


from base64 import b64encode
from html import escape

def main(inputs: dict, context):
  index_list: list[str] = []
  for name in inputs["names"]:
    index_list.append(f"<li><a href=\"./{name}.html\">{escape(name)}</a></li>")
  file_content = f'''
<html>
  <head>
    <title>目录</title>
  </head>
  <body>
    <h1>目录</h1>
    <ul>
      {"\n      ".join(index_list)}
    </ul>
  </body>
</html>
'''
  binary = b64encode(file_content.encode("utf-8")).decode("utf-8")

  context.output("index.html", "file_name", False)
  context.output(binary, "binary", False)
  context.done()


import re
import pdfplumber

from dataclasses import dataclass
from enum import Enum
from typing import Callable

def main(inputs: dict, context):
  begin_page_index = inputs["begin_page"] - 1
  end_page_index = inputs["end_page"] - 1

  latest_kind: PageItemKind = PageItemKind.Body
  title_text_list: list[str] = []
  body_text_list: list[str] = []
  quote_list: list[dict] = []
  names: list[str] = []

  with pdfplumber.open(inputs.get("pdf_path")) as pdf:
    for page_index, pdf_page in enumerate(pdf.pages):
      if page_index < begin_page_index or page_index > end_page_index:
        continue

      page = extract_page_item(pdf_page, inputs)
      if page is None:
        continue

      quotes = convert_quotes_to_map(page.quote, inputs["quote_list"])
      
      for item in page.items:
        if latest_kind != item.kind:
          latest_kind = item.kind
          if item.kind == PageItemKind.Title:
            wiki = output_wiki(context, title_text_list, body_text_list, quote_list)
            title_text_list.clear()
            body_text_list.clear()
            quote_list.clear()
            if wiki is not None:
              names.append(wiki["file_name"])

        text_list: list[str]

        if item.kind == PageItemKind.Title:
          text_list = title_text_list
        elif item.kind == PageItemKind.Body:
          text_list = body_text_list

        if item.is_link_previous and len(text_list) > 0:
          for i, text in enumerate(item.text):
            pretext_len = 0
            if i == 0:
              pretext_len = len(text_list)
              text_list[-1] += text
            else:
              text_list.append(text)
            if item.kind == PageItemKind.Body:
              pick_quotes(text, quotes, lambda offset, quote_text: quote_list.append({
                "index": len(text_list) - 1,
                "offset": pretext_len + offset,
                "text": quote_text,
              }))
        else:
          for text in item.text:
            text_list.append(text)
            pick_quotes(text, quotes, lambda offset, quote_text: quote_list.append({
              "index": len(text_list) - 1,
              "offset": offset,
              "text": quote_text,
            }))

  if len(title_text_list) > 0 and len(body_text_list) > 0:
    wiki = output_wiki(context, title_text_list, body_text_list, quote_list)
    if wiki is not None:
      names.append(wiki["file_name"])

  context.output(names, "names", True)

def pick_quotes(text: str, quotes: dict[str, str], func: Callable[[int, str], None]):
  for i, char in enumerate(text):
    if char in quotes:
      quote_text = quotes[char]
      func(i, quote_text)

def output_wiki(context, title_text_list: list[str], body_text_list: list[str], quote_list: list[dict]):
  if len(title_text_list) <= 0:
    return None

  title: str = title_text_list[0]
  description: str = ""
  if len(title_text_list) > 1:
    description = title_text_list[1]
  text_list = body_text_list[:]
  wiki: dict = {
    "title": title,
    "file_name": escape_filename(title),
    "description": description,
    "text_list": text_list,
    "quote_list": quote_list,
  }
  context.output(wiki, "wiki", False)
  return wiki

class PageItemKind(Enum):
  Title = 1
  Body = 2

@dataclass
class PageItem:
  kind: PageItemKind
  text: list[str]
  is_link_previous: bool

@dataclass
class Page:
  items: list[PageItem]
  quote: list[str]

def extract_page_item(page, inputs: dict) -> Page:
  quote_max_size = inputs.get("quote_max_size")
  title_max_length = inputs.get("title_max_length")
  grouped_paragraphs = extract_grouped_paragraphs(page, inputs)

  if len(grouped_paragraphs) == 0:
    return None

  footer_paragraphs = grouped_paragraphs[-1]
  quote: list[str]

  if footer_paragraphs.size <= quote_max_size:
    del grouped_paragraphs[-1]
    quote = footer_paragraphs.text_list
  else:
    quote = []

  items: list[PageItem] = []
  for paragraph in grouped_paragraphs:
    text_list: list[str] = paragraph.text_list
    kind: PageItemKind
    if len(text_list) == 2 and len(text_list[0]) <= title_max_length:
      kind = PageItemKind.Title
    else:
      kind = PageItemKind.Body
    items.append(PageItem(
      kind=kind,
      text=text_list,
      is_link_previous=paragraph.is_link_previous,
    ))
  return Page(items=items, quote=quote)

@dataclass
class Paragraphs:
  text_list: list[str]
  is_link_previous: bool
  size: float

def extract_grouped_paragraphs(page, inputs: dict) -> list[Paragraphs]:
  quote_list = inputs.get("quote_list")
  quote_max_size = inputs.get("quote_max_size")
  paragraph_head_max_delta = inputs.get("paragraph_head_max_delta")
  max_height_diff = inputs.get("max_height_diff")
  title_max_length = inputs.get("title_max_length")

  grouped_paragraphs: list[Paragraphs] = []
  lines = page.extract_text_lines()
  lines = [x for x in lines if not is_empty_text(x["text"])]

  if len(lines) == 0:
    return grouped_paragraphs

  # 删除第一组，这是页眉
  del lines[0]

  for lines in group_lines(lines, max_height_diff):
    text_list: list[str] = []
    tags = tag_head_for_lines(lines, quote_list, quote_max_size, paragraph_head_max_delta)

    if len(tags) == 0:
      continue

    if is_title_tags(tags) and len(lines[0]["text"]) <= title_max_length:
      for line in lines:
        text_list.append(line["text"])
    else:
      for i, line in enumerate(lines):
        tag = tags[i]
        if not tag.is_out:
          text = line["text"]
          if tag.is_head or len(text_list) == 0:
            text_list.append(text)
          else:
            pretext = text_list[-1]
            pretext = re.sub(r"-$", "", pretext) # 删掉英语单词连接符
            text_list[-1] = pretext + text

    mean_size = 0.0
    for tag in tags:
      mean_size += tag.size
    mean_size /= len(tags)

    grouped_paragraphs.append(Paragraphs(
      text_list=text_list,
      is_link_previous=not tags[0].is_head,
      size=mean_size,
    ))

  return grouped_paragraphs

def is_title_tags(tags: list) -> bool:
  if len(tags) != 2:
    return False
  if tags[0].is_head != False or tags[1].is_head != False:
    return False
  return True

def group_lines(lines: list, max_height_diff: int) -> list[list]:
  if len(lines) == 0:
    return []

  height_diff_list: list[int] = []
  grouped_lines: list[list] = []

  for i, line in enumerate(lines[1:], start=1):
    prev_top = lines[i - 1]["top"]
    top = line["top"]
    height_diff_list.append(top - prev_top)

  current_grouped_lines: list = [lines[0]]

  for i, height_diff in enumerate(height_diff_list[1:], start=1):
    prev_height_diff = height_diff_list[i - 1]
    diff_diff = height_diff - prev_height_diff

    if diff_diff < 0 and abs(diff_diff) > max_height_diff:
      if len(current_grouped_lines) > 0:
        grouped_lines.append(current_grouped_lines)
      current_grouped_lines = [lines[i]]
    elif diff_diff > 0 and diff_diff > max_height_diff:
      current_grouped_lines.append(lines[i])
      grouped_lines.append(current_grouped_lines)
      current_grouped_lines = []
    else:
      current_grouped_lines.append(lines[i])

  current_grouped_lines.append(lines[-1])
  grouped_lines.append(current_grouped_lines)

  return grouped_lines

@dataclass
class LineTag:
  is_head: bool
  is_out: bool
  size: float

def tag_head_for_lines(
  lines: list, 
  quote_list: str, 
  quote_max_size: float,
  paragraph_head_max_delta: int,
) -> list[LineTag]:
  tags: list[LineTag] = []
  mean_x0 = 0.0
  mean_size = 0.0

  for line in lines:
    tag = LineTag(
      is_head=False, 
      is_out=False,
      size=0.0
    )
    mean_x0 += line["x0"]
    tags.append(tag)
    chars = line["chars"]

    for char in chars:
      tag.size += char["size"]
    tag.size /= len(chars)
    mean_size += tag.size

  mean_x0 /= len(lines)
  mean_size /= len(lines)

  if len(lines) <= 1:
    for tag in tags:
      tag.is_head = False

  elif mean_size <= quote_max_size:
    for i, line in enumerate(lines):
      sign = get_quote_sign(line["text"], quote_list)
      tags[i].is_head = (sign != "")

  elif len(lines) == 2:
    if abs(lines[0]["x0"] - lines[1]["x0"]) <= tags[0].size:
      # 两者间隔不超过一个字符的宽度，说明客观上，它们之间没有间隔太远
      tags[0].is_head = False
      tags[1].is_head = False
    else:
      tags[0].is_head = True
      tags[1].is_head = True

  else:
    on_left_count = 0
    for i, line in enumerate(lines):
      is_head = line["x0"] > mean_x0
      tags[i].is_head = is_head
      if is_head:
        on_left_count += 1
    if 2 * on_left_count > len(lines):
      for tag in tags:
        tag.is_head = not tag.is_head

  mean_not_head_x0 = 0.0
  not_head_count = 0.0

  for i, tag in enumerate(tags):
    if not tag.is_head:
      mean_not_head_x0 += lines[i]["x0"]
      not_head_count += 1.0

  if not_head_count > 0.0:
    mean_not_head_x0 /= not_head_count
    for i, tag in enumerate(tags):
      if abs(lines[i]["x0"] - mean_not_head_x0) > paragraph_head_max_delta:
        tag.is_out = True

  return tags

def convert_quotes_to_map(quotes: list[str], quote_list: str) -> dict[str, str]:
  quotes_dict: dict[str, str] = {}

  for quote in quotes:
    quote = quote.lstrip()
    if quote == "":
      continue
    sign = get_quote_sign(quote, quote_list)
    if sign == "":
      continue
    quotes_dict[sign] = quote[1:].lstrip()
 
  return quotes_dict

def get_quote_sign(text: str, quote_list: str) -> str:
  for sign in quote_list:
    if sign == text[0]:
      return sign
  return ""

def is_empty_text(text: str):
  return re.match(r"^\s*$", text)

def escape_filename(filename):
  illegal_chars = r'[<>:"/\\|?*\x00-\x1F\x7F-\x9F]'
  escaped_filename = re.sub(illegal_chars, " ", filename)
  escaped_filename = re.sub(r"\s+", " ", escaped_filename)
  escaped_filename = escaped_filename.strip()
  escaped_filename = escaped_filename.replace(" ", "_")
  return escaped_filename
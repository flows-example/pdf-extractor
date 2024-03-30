import re
import pdfplumber

from dataclasses import dataclass
from enum import Enum

def main(inputs: dict, context):
  pdf_path = inputs.get("pdf_path")
  with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
      print("================")
      grouped_paragraphs = extract_grouped_paragraphs(page, inputs)
      for paragraph in grouped_paragraphs:
        print(">>>>", paragraph.is_link_previous)
        for p in paragraph.text_list:
          print(p)

  context.done()

class PageItemKind(Enum):
  Title = 1
  Quote = 2
  Body = 3

@dataclass
class PageItem:
  kind: PageItemKind
  text: str
  is_head: bool

@dataclass
class Paragraphs:
  text_list: list[str]
  is_link_previous: bool

def extract_grouped_paragraphs(page, inputs: dict) -> list[Paragraphs]:
  paragraph_head_max_delta = inputs.get("paragraph_head_max_delta")
  max_height_diff = inputs.get("max_height_diff")

  grouped_paragraphs: list[Paragraphs] = []
  lines = page.extract_text_lines()
  lines = [x for x in lines if not is_empty_text(x["text"])]

  for lines in group_lines(lines, max_height_diff):
    text_list: list[str] = []
    tags = tag_head_for_lines(lines, paragraph_head_max_delta)

    if len(tags) == 0:
      continue

    for i, line in enumerate(lines):
      text = line["text"]
      tag = tags[i]

      if not tag.is_out:
        if tag.is_head or len(text_list) == 0:
          text_list.append(text)
        else:
          pretext = text_list[-1]
          pretext = re.sub(r"-$", "", pretext) # 删掉英语单词连接符
          text_list[-1] = pretext + text

    grouped_paragraphs.append(Paragraphs(
      text_list=text_list,
      is_link_previous=not tags[0].is_head,
    ))

  return grouped_paragraphs

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

def tag_head_for_lines(lines: list, paragraph_head_max_delta: int) -> list[LineTag]:
  tags: list[LineTag] = []
  mean_x0 = 0.0

  for line in lines:
    mean_x0 += line["x0"]
    tags.append(LineTag(
      is_head=False, 
      is_out=False,
    ))
  mean_x0 /= len(lines)

  if len(lines) <= 2:
    # 只有两行，无法通过缩进比较，从中文的习惯来看，就是 2 个自然段。
    for tag in tags:
      tag.is_head = True
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

def is_empty_text(text: str):
  return re.match(r"^\s*$", text)
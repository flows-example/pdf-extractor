

def main(props: dict, context):
  props_in = props.get("in")
  print(props_in)
  # your code here
  context.output("result value", "out", True)


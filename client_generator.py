#!/usr/bin/env python3
import sys
import re
import yaml

def snake_case(text: str) -> str:
    """Convert path-like strings or HTTP verbs into snake_case."""
    return re.sub(r'[^0-9a-zA-Z]+', '_', text).strip('_').lower()

def sanitize_param_name(param_name: str) -> str:
    """
    Make sure param_name is a valid Python identifier:
      - Replace any bracket-like 'foo[bar]' with 'foo_bar'
      - If it starts with a digit, prepend something like 'p_'
      - If it's a reserved word (e.g. 'class', 'def'), add a suffix
    """
    # 1) Replace [ and ] with underscores
    new_name = param_name.replace('[', '_').replace(']', '')

    # 2) If name starts with a digit, prepend 'p_'
    if re.match(r'^[0-9]', new_name):
        new_name = f"p_{new_name}"

    # 3) If any leftover non-identifier chars, convert to underscores
    #    e.g. "concordance_query[char]" => "concordance_query_char"
    new_name = re.sub(r'[^0-9a-zA-Z_]', '_', new_name)

    # 4) Handle Python reserved keywords if you wish
    python_keywords = {
        'class', 'def', 'return', 'lambda', 'for', 'while', 'break', 'continue',
        'pass', 'import', 'global', 'with', 'yield', 'except', 'raise', 'from',
        'as', 'if', 'elif', 'else', 'try', 'finally', 'nonlocal', 'assert',
        'del', 'in', 'and', 'or', 'not', 'is', 'None', 'True', 'False'
    }
    if new_name in python_keywords:
        new_name += '_param'

    return new_name


def resolve_ref(ref_obj: dict, root_spec: dict) -> dict:
    """Resolve $ref references in the spec."""
    if '$ref' not in ref_obj:
        return ref_obj
    ref_path = ref_obj['$ref']
    if not ref_path.startswith('#/'):
        raise ValueError(f"Unsupported $ref format: {ref_path}")
    path_parts = ref_path[2:].split('/')
    node = root_spec
    for part in path_parts:
        node = node[part]
    return node


def generate_function_name(method: str, path: str) -> str:
    """Create a function name from the HTTP method and path."""
    return f"{method.lower()}_{snake_case(path)}"


def path_to_fstring(path_str, path_params):
    """
    Convert OpenAPI path with {param} placeholders into an f-string for Python.
    Example: /ca/api/corpora/{corpusId} => f"/ca/api/corpora/{corpusId}"
    """
    newpath = path_str
    for param in path_params:
        placeholder = '{' + param + '}'
        # if placeholder is in path, convert to {param} in f-string
        if placeholder in newpath:
            newpath = newpath.replace(placeholder, f'{{{param}}}')
    return newpath

def build_function_code(func_name: str, method: str, path: str, parameters: list,
                        base_url: str, root_spec: dict) -> str:
    """
    Build Python code for one function that calls the endpoint.

    We:
      1. Resolve $ref,
      2. Collect path vs. query parameters,
      3. Sanitize duplicates,
      4. Create docstrings,
      5. Create function signature,
      6. Generate the 'params' dict for query params,
      7. Return code as a string.
    """
    resolved_params = []
    for p in parameters:
        p_resolved = resolve_ref(p, root_spec)
        resolved_params.append(p_resolved)

    path_params = []
    query_params = []
    doc_lines = [f'"""{method.upper()} {path}', "Parameters:"]

    # We'll keep a list of all param names to detect duplicates
    used_names = {}

    def get_unique_name(name: str) -> str:
        """
        Return a sanitized name that doesn't collide with existing ones.
        For collisions, we'll append _2, _3, etc.
        """
        base = sanitize_param_name(name)
        candidate = base
        index = 2
        while candidate in used_names:
            # If it is already used, increment suffix
            candidate = f"{base}_{index}"
            index += 1
        used_names[candidate] = True
        return candidate

    # We store (py_name, openapi_name, location, description).
    path_param_list = []
    query_param_list = []

    for p in resolved_params:
        p_in = p.get('in', 'query')
        p_name = p.get('name', 'param')
        desc  = p.get('description', '')

        py_name = get_unique_name(p_name)  # sanitize for Python
        doc_lines.append(f"  :param {py_name}: ({p_in}) {desc}".rstrip())

        if p_in == 'path':
            path_param_list.append((py_name, p_name))
        elif p_in == 'query':
            query_param_list.append((py_name, p_name))

    doc_lines.append('"""')
    docstring = "\n".join(doc_lines)

    # path param => required
    # query param => optional= None
    sig_parts = []
    for (py_name, _) in path_param_list:
        sig_parts.append(py_name)  # required
    for (py_name, _) in query_param_list:
        sig_parts.append(f"{py_name}=None")

    signature = ", ".join(sig_parts)

    # Build the path with f-string for path placeholders
    # We'll use the sanitized Python names (py_name) in an f-string
    # But we only do .format for the placeholders that match the original openapi_name
    # i.e. corpusId -> {corpusId}
    # We'll do a quick map from py_name -> original openapi_name
    path_map = {py: orig for (py, orig) in path_param_list}
    # We'll generate a “fake” param placeholder for the final URL
    # We'll do the substitution after we build the function line
    # Or we can just do newpath = path_to_fstring(path, [original_name ...]).
    # But the user in Python will pass py_name. 
    # We'll do a small trick: 
    f_str_path = path
    for (py_name, orig_name) in path_param_list:
        f_str_path = f_str_path.replace('{'+orig_name+'}', f'{{{py_name}}}')
    url_line = f"url = f\"{base_url}{f_str_path}\""

    # Build dict of query params
    if query_param_list:
        # 'openapi_name': python_var
        # but we need to map python_var to the user’s variable name
        # e.g. 'corpname': corpname
        items = []
        for (py_name, openapi_name) in query_param_list:
            items.append(f"'{openapi_name}': {py_name}")
        indent_str = "    "
        params_code = "params = {\n" + indent_str + (",\n"+indent_str).join(items) + "\n}"
    else:
        params_code = "params = None"

    method_lower = method.lower()
    lines = [
        f"def {func_name}({signature}):",
        f"    {docstring}",
        f"    {url_line}",
        f"    {params_code}",
        f"    response = requests.{method_lower}(url, params=params)",
        f"    return response\n"
    ]
    return "\n".join(lines)


def generate_api_client_from_openapi(openapi_spec_path: str, output_file: str = "generated_sketchengine_client.py"):
    with open(openapi_spec_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    servers = spec.get("servers", [])
    if servers and isinstance(servers, list) and 'url' in servers[0]:
        base_url = servers[0]['url'].rstrip('/')
    else:
        base_url = "https://api.sketchengine.eu"

    paths = spec.get("paths", {})
    lines = []
    lines.append("# This file is AUTO-GENERATED by generate_sketchengine_api.py")
    lines.append("import requests\n")

    for path, path_item in paths.items():
        for method, method_obj in path_item.items():
            if method.lower() not in ['get','post','put','patch','delete','head','options']:
                continue

            # combine path-level + operation-level parameters
            path_params = path_item.get('parameters', [])
            op_params   = method_obj.get('parameters', [])
            all_params = path_params + op_params

            func_name = generate_function_name(method, path)
            func_code = build_function_code(
                func_name=func_name,
                method=method,
                path=path,
                parameters=all_params,
                base_url=base_url,
                root_spec=spec
            )
            lines.append(func_code)

    with open(output_file, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(lines))

    print(f"Generated {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_sketchengine_api.py openapi.yaml [output_file.py]")
        sys.exit(1)
    openapi_spec_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = "generated_sketchengine_client.py"

    generate_api_client_from_openapi(openapi_spec_path, output_file)


if __name__ == "__main__":
    main()
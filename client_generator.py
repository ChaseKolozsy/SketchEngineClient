#!/usr/bin/env python3
import sys
import re
import yaml
import os

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

    # 3) Convert leftover non-identifier chars to underscores
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
    if not isinstance(ref_obj, dict):
        return ref_obj
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


def build_path_fstring(path_str: str, path_params: list) -> str:
    """
    Convert OpenAPI path with {param} placeholders into an f-string for Python.
    E.g., /ca/api/corpora/{corpusId} => f"/ca/api/corpora/{corpusId}"
    We'll replace each {originalName} with {pyName} (since we sanitize them).
    """
    result = path_str
    for orig_name, py_name in path_params:
        placeholder = '{' + orig_name + '}'
        if placeholder in result:
            result = result.replace(placeholder, f'{{{py_name}}}')
    return result


def get_content_type(method_obj: dict) -> str:
    """
    Retrieve the first content type from requestBody if present.
    Returns something like 'application/json' or 'multipart/form-data', or None.
    """
    if 'requestBody' not in method_obj:
        return None
    rb = method_obj['requestBody']
    rb_resolved = resolve_ref(rb, method_obj)  # if the requestBody has $ref
    content = rb_resolved.get('content', {})
    if not content:
        return None
    # Just pick the first content type available
    # Or pick in priority order if you prefer
    first_key = list(content.keys())[0]
    return first_key


def parse_request_body_fields(method_obj: dict, root_spec: dict) -> list:
    """
    Inspect the requestBody and attempt to parse it for form fields, etc.
    We return a list of tuples: (py_name, openapi_name, is_file, description).
    This is a simple approach; for more complex specs, you'd expand logic here.
    """
    if 'requestBody' not in method_obj:
        return []

    rb = method_obj['requestBody']
    rb = resolve_ref(rb, root_spec)
    content = rb.get('content', {})

    # We'll assume schema => properties for application/json or form-data
    # For complex schemas, you'd do more thorough inspection
    if not content:
        return []

    # For simplicity, pick first:
    first_ct = list(content.keys())[0]
    schema = content[first_ct].get('schema', {})
    schema = resolve_ref(schema, root_spec)

    # If it's an object with 'properties', we can generate param names
    if schema.get('type') == 'object':
        props = schema.get('properties', {})
        results = []
        for prop_name, prop_obj in props.items():
            prop_obj = resolve_ref(prop_obj, root_spec)
            desc = prop_obj.get('description', '')
            # If there's format: binary, we might guess it's file
            # or if the property is named 'file' => is_file
            is_file = (prop_obj.get('format') == 'binary')
            py_name = sanitize_param_name(prop_name)
            results.append((py_name, prop_name, is_file, desc))
        return results

    # Otherwise just return empty or handle other patterns
    return []


def build_function_code(func_name: str,
                        method: str,
                        path: str,
                        path_params_in_spec: list,
                        query_params_in_spec: list,
                        request_body_fields: list,
                        content_type: str,
                        root_spec: dict,
                        base_url: str) -> str:
    """
    Builds the python code for a single operation.

    path_params_in_spec: list of (py_name, openapi_name, description)
    query_params_in_spec: list of (py_name, openapi_name, description)
    request_body_fields: list of (py_name, openapi_name, is_file, description)
    content_type: e.g. 'application/json' or 'multipart/form-data'
    """
    # docstring lines
    doc_lines = [f'"""{method.upper()} {path}', "Parameters:"]
    sig_parts = ['self']

    # 1) Required path params
    for py_name, openapi_name, desc in path_params_in_spec:
        doc_lines.append(f"  :param {py_name}: (path) {desc}")
        sig_parts.append(py_name)  # required

    # 2) Optional query params
    for py_name, openapi_name, desc in query_params_in_spec:
        doc_lines.append(f"  :param {py_name}: (query) {desc}")
        sig_parts.append(f"{py_name}=None")

    # 3) requestBody fields => the same approach
    if request_body_fields:
        if content_type == 'application/json':
            doc_lines.append("  (Body is application/json)")
            for (py_name, openapi_name, is_file, desc) in request_body_fields:
                doc_lines.append(f"  :param {py_name}: (json) {desc}")
                sig_parts.append(f"{py_name}=None")
        elif content_type == 'multipart/form-data':
            doc_lines.append("  (Body is multipart/form-data)")
            for (py_name, openapi_name, is_file, desc) in request_body_fields:
                if is_file:
                    doc_lines.append(f"  :param {py_name}: (file) {desc}")
                else:
                    doc_lines.append(f"  :param {py_name}: (form) {desc}")
                sig_parts.append(f"{py_name}=None")

    doc_lines.append('"""')
    docstring = "\n".join(doc_lines)

    # Build path f-string
    # path_params_in_spec is a list of (py_name, orig_name, desc)
    # we need (orig_name, py_name)
    path_param_map = [(original, py) for (py, original, _) in path_params_in_spec]
    f_str_path = build_path_fstring(path, path_param_map)
    endpoint_line = f"endpoint = f\"{f_str_path}\""

    # Build the "params" dict from query params
    if query_params_in_spec:
        param_lines = []
        param_lines.append("params = {")
        for py_name, openapi_name, _ in query_params_in_spec:
            param_lines.append(f"    '{openapi_name}': {py_name},")
        param_lines.append("}")
        param_lines.append("# Filter out None values")
        param_lines.append("params = {k: v for k, v in params.items() if v is not None}")
        params_code = "\n    ".join(param_lines)
    else:
        params_code = "params = None"

    # Build request body code if needed
    if method.lower() in ['post', 'put', 'patch'] and content_type == 'multipart/form-data':
        lines = []
        lines.append(f"def {func_name}({', '.join(sig_parts)}):")
        lines.append(f"    {docstring}")
        lines.append(f"    {endpoint_line}")
        lines.append(f"    {params_code}")
        lines.append("    files = {}")
        lines.append("    form_data = {}")
        
        # Handle each field based on whether it's a file or form data
        for py_name, openapi_name, is_file, _ in request_body_fields:
            lines.append(f"    if {py_name} is not None:")
            if is_file:
                lines.append(f"        files['{openapi_name}'] = {py_name}")
            else:
                lines.append(f"        form_data['{openapi_name}'] = str({py_name})")
        
        lines.append("    if not form_data:")
        lines.append("        form_data = None")
        lines.append("    if not files:")
        lines.append("        files = None")
        lines.append("    return self.make_request(")
        lines.append(f"        '{method.lower()}',")
        lines.append("        endpoint,")
        lines.append("        params=params,")
        lines.append("        data=form_data,")
        lines.append("        files=files")
        lines.append("    )")
        lines.append("")
        return "\n".join(lines)
    else:
        # Build final method lines for non-multipart requests
        lines = []
        lines.append(f"def {func_name}({', '.join(sig_parts)}):")
        lines.append(f"    {docstring}")
        lines.append(f"    {endpoint_line}")
        lines.append(f"    {params_code}")
        
        # Handle JSON request body if needed
        if method.lower() in ['post', 'put', 'patch'] and content_type == 'application/json' and request_body_fields:
            data_lines = []
            data_lines.append("data = {")
            for py_name, openapi_name, is_file, _ in request_body_fields:
                data_lines.append(f"    '{openapi_name}': {py_name},")
            data_lines.append("}")
            data_lines.append("# Filter out None values")
            data_lines.append("data = {k: v for k, v in data.items() if v is not None}")
            lines.append("    " + "\n    ".join(data_lines))
        else:
            lines.append("    data = None")
        
        lines.append("    return self.make_request(")
        lines.append(f"        '{method.lower()}', endpoint, params=params, data=data")
        lines.append("    )")
        lines.append("")
        return "\n".join(lines)


def generate_api_client_from_openapi(openapi_spec_path: str, output_file: str = "generated_sketchengine_client.py"):
    with open(openapi_spec_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    servers = spec.get("servers", [])
    if servers and isinstance(servers, list) and 'url' in servers[0]:
        base_url = servers[0]['url'].rstrip('/')
    else:
        base_url = "https://api.sketchengine.eu"

    lines = []
    lines.append("# This file is AUTO-GENERATED by generate_sketchengine_api.py")
    lines.append("import requests")
    lines.append("import os\n")

    lines.extend([
        "class SketchEngineClient:",
        f"    BASE_URL = \"{base_url}\"",
        "",
        "    def __init__(self, api_key=None):",
        "        self.api_key = api_key or os.environ.get('SKETCH_ENGINE_API_KEY')",
        "        if not self.api_key:",
        "            raise ValueError(\"API key must be provided either directly or through SKETCH_ENGINE_API_KEY environment variable\")",
        "",
        "        self.session = requests.Session()",
        "        self.session.headers.update({",
        "            'Authorization': f'Bearer {self.api_key}'",
        "        })",
        "",
        "    def make_request(self, method, endpoint, params=None, data=None, files=None):",
        "        \"\"\"",
        "        Make a request to the Sketch Engine API",
        "",
        "        Args:",
        "            method (str): HTTP method ('GET', 'POST', etc.)",
        "            endpoint (str): API endpoint path (f-string expansion included)",
        "            params (dict, optional): Query parameters",
        "            data (dict or None, optional): JSON or form data (for multipart, pass as data=form_data) ",
        "            files (dict or None, optional): For file uploads in multipart. e.g. {'file': (filename, fileobj)} ",
        "",
        "        Returns:",
        "            requests.Response: Response from the API",
        "        \"\"\"",
        "        url = f\"{self.BASE_URL}{endpoint}\"",
        "        try:",
        "            if files:",
        "                # multipart form-data likely",
        "                response = self.session.request(method=method, url=url, params=params, data=data, files=files)",
        "            else:",
        "                # normal JSON or query",
        "                # if method in POST/PUT/PATCH and data => send as JSON?",
        "                if method.upper() in ['POST','PUT','PATCH'] and isinstance(data, dict) and not files:",
        "                    # We'll just guess it's JSON. You might want a special check here.",
        "                    response = self.session.request(method=method, url=url, params=params, json=data)",
        "                else:",
        "                    response = self.session.request(method=method, url=url, params=params, json=data)",
        "            response.raise_for_status()",
        "            return response",
        "        except requests.exceptions.RequestException as e:",
        "            raise",
        "\n"
    ])

    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        # path-level params
        path_params_def = path_item.get('parameters', [])

        for method, method_obj in path_item.items():
            if method.lower() not in ['get','post','put','patch','delete','head','options']:
                continue
            if not isinstance(method_obj, dict):
                continue

            # operation-level parameters
            op_params_def = method_obj.get('parameters', [])

            # Unify duplicates by (in, name)
            all_params_dict = {}
            for p in (path_params_def + op_params_def):
                p_resolved = resolve_ref(p, spec)
                p_in = p_resolved.get('in')
                p_name = p_resolved.get('name')
                if not p_in or not p_name:
                    continue
                key = (p_in, p_name)
                all_params_dict[key] = p_resolved

            # Convert back to list and process
            path_params_in_spec = []
            query_params_in_spec = []

            for param_def in all_params_dict.values():
                p_in = param_def.get('in', '')
                p_name = param_def.get('name', '')
                desc = param_def.get('description', '')
                py_name = sanitize_param_name(p_name)
                
                if p_in == 'path':
                    path_params_in_spec.append((py_name, p_name, desc))
                elif p_in == 'query':
                    query_params_in_spec.append((py_name, p_name, desc))

            # Now check for requestBody
            ct = get_content_type(method_obj)
            rb_fields = parse_request_body_fields(method_obj, spec)

            func_name = generate_function_name(method, path)
            func_code = build_function_code(
                func_name=func_name,
                method=method,
                path=path,
                path_params_in_spec=path_params_in_spec,
                query_params_in_spec=query_params_in_spec,
                request_body_fields=rb_fields,
                content_type=ct,
                root_spec=spec,
                base_url=base_url
            )
            # Indent the function code for class scope
            indented = []
            for line in func_code.split('\n'):
                indented.append("    " + line)
            lines.extend(indented)

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
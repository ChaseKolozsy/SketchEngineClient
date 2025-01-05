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
      - Replace bracket-like 'foo[bar]' with 'foo_bar'
      - If it starts with a digit, prepend something
      - If it's a reserved word, add a suffix
    """
    new_name = param_name.replace('[', '_').replace(']', '')
    if re.match(r'^[0-9]', new_name):
        new_name = f"p_{new_name}"
    new_name = re.sub(r'[^0-9a-zA-Z_]', '_', new_name)

    python_keywords = {
        'class', 'def', 'return', 'lambda', 'for', 'while', 'break', 'continue',
        'pass', 'import', 'global', 'with', 'yield', 'except', 'raise', 'from',
        'as', 'if', 'elif', 'else', 'try', 'finally', 'nonlocal', 'assert',
        'del', 'in', 'and', 'or', 'not', 'is', 'None', 'True', 'False'
    }
    if new_name in python_keywords:
        new_name += '_param'
    return new_name

def resolve_ref(ref_obj, root_spec):
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

def generate_function_name(method, path):
    return f"{method.lower()}_{snake_case(path)}"

def build_path_fstring(path_str, path_params):
    """Turn {origName} placeholders into {pyName} in an f-string."""
    result = path_str
    for (orig, py) in path_params:
        placeholder = '{' + orig + '}'
        if placeholder in result:
            result = result.replace(placeholder, f'{{{py}}}')
    return result

def get_first_content_type(method_obj):
    """Return first content type or None."""
    if 'requestBody' not in method_obj:
        return None
    rb = method_obj['requestBody']
    content = rb.get('content', {})
    if not content:
        return None
    return list(content.keys())[0]  # just pick first

def parse_request_body_fields(method_obj, root_spec):
    """
    Return a list of (py_name, openapi_name, is_file, description, required, is_array_of_files)
    so we can handle multi-file if needed.
    """
    if 'requestBody' not in method_obj:
        return []

    rb = method_obj['requestBody']
    rb = resolve_ref(rb, root_spec)
    content = rb.get('content', {})
    if not content:
        return []

    # just pick first
    first_ct = list(content.keys())[0]
    schema = content[first_ct].get('schema', {})
    schema = resolve_ref(schema, root_spec)

    if schema.get('type') != 'object':
        # you could expand logic for array or something else
        return []

    props = schema.get('properties', {})
    required_fields = schema.get('required', [])  # list of strings

    results = []
    for prop_name, prop_obj in props.items():
        prop_obj = resolve_ref(prop_obj, root_spec)
        desc = prop_obj.get('description', '')
        is_file = (prop_obj.get('format') == 'binary')
        is_array_of_files = False

        # if the schema says type: array + items.format == binary => multi-file
        if prop_obj.get('type') == 'array':
            items_obj = resolve_ref(prop_obj.get('items', {}), root_spec)
            if items_obj.get('format') == 'binary':
                is_file = True
                is_array_of_files = True

        py_name = sanitize_param_name(prop_name)
        param_required = (prop_name in required_fields)
        results.append((py_name, prop_name, is_file, desc, param_required, is_array_of_files))
    return results

def build_function_code(func_name,
                        method,
                        path,
                        path_params_in_spec,
                        query_params_in_spec,
                        request_body_fields,
                        content_type,
                        root_spec,
                        base_url):
    # docstring lines
    doc_lines = [f'"""{method.upper()} {path}', "Parameters:"]
    sig_parts = ['self']

    # For each path param
    for (py_name, openapi_name, desc, required) in path_params_in_spec:
        # doc line
        doc_lines.append(f"  :param {py_name}: (path) {desc}")
        # signature => no default if required, else =None
        if required:
            sig_parts.append(f"{py_name}")
        else:
            sig_parts.append(f"{py_name}=None")

    # For each query param
    for (py_name, openapi_name, desc, required) in query_params_in_spec:
        doc_lines.append(f"  :param {py_name}: (query) {desc}")
        if required:
            sig_parts.append(f"{py_name}")
        else:
            sig_parts.append(f"{py_name}=None")

    # For request body fields
    if request_body_fields:
        if content_type == 'application/json':
            doc_lines.append("  (Body is application/json)")
            for (py_name, openapi_name, is_file, desc, required, is_array_of_files) in request_body_fields:
                if required:
                    sig_parts.append(py_name)  # no default => must pass
                else:
                    sig_parts.append(f"{py_name}=None")
                doc_lines.append(f"  :param {py_name}: (json) {desc}")
        elif content_type == 'multipart/form-data':
            doc_lines.append("  (Body is multipart/form-data)")
            for (py_name, openapi_name, is_file, desc, required, is_array_of_files) in request_body_fields:
                if required:
                    sig_parts.append(py_name)
                else:
                    sig_parts.append(f"{py_name}=None")
                if is_file and not is_array_of_files:
                    doc_lines.append(f"  :param {py_name}: (file) single file => (filename, fileobj)")
                elif is_file and is_array_of_files:
                    doc_lines.append(f"  :param {py_name}: (files) multiple files => list of (filename, fileobj)")
                else:
                    doc_lines.append(f"  :param {py_name}: (form) {desc}")

    doc_lines.append('"""')
    docstring = "\n".join(doc_lines)

    # Build path f-string
    path_map = [(orig, py) for (py, orig, _, _) in path_params_in_spec]
    f_str_path = build_path_fstring(path, path_map)
    endpoint_line = f"endpoint = f\"{f_str_path}\""

    # Build the "params" dict from query params
    if query_params_in_spec:
        param_lines = []
        param_lines.append("params = {")
        for (py_name, openapi_name, _, _) in query_params_in_spec:
            param_lines.append(f"    '{openapi_name}': {py_name},")
        param_lines.append("}")
        param_lines.append("# Filter out None values")
        param_lines.append("params = {k: v for k, v in params.items() if v is not None}")
        params_code = "\n    ".join(param_lines)
    else:
        params_code = "params = None"

    # Now let's build required checks for path + query
    required_checks = []
    for (py_name, openapi_name, desc, required) in path_params_in_spec + query_params_in_spec:
        if required:
            required_checks.append(f"if {py_name} is None: raise ValueError(\"Parameter '{py_name}' is required.\")")

    # Build request body code
    data_code = "data = None"
    files_code = "files = None"
    body_required_checks = []

    if method.lower() in ['post','put','patch'] and request_body_fields:
        if content_type == 'application/json':
            # We'll build a dict
            lines_rb = ["data = {}", "files = None"]
            for (py_name, openapi_name, is_file, desc, required, is_array_of_files) in request_body_fields:
                # Add check if required
                if required:
                    body_required_checks.append(f"if {py_name} is None: raise ValueError(\"Body field '{py_name}' is required.\")")

                lines_rb.append(f"if {py_name} is not None:")
                lines_rb.append(f"    data['{openapi_name}'] = {py_name}")
            lines_rb.append("# Filter out None values in data dict")
            lines_rb.append("data = {k: v for k, v in data.items() if v is not None}")
            data_code = "\n    ".join(lines_rb)

        elif content_type == 'multipart/form-data':
            lines_rb = [
                "files = {}",
                "form_data = {}"
            ]
            for (py_name, openapi_name, is_file, desc, required, is_array_of_files) in request_body_fields:
                if required:
                    body_required_checks.append(f"if {py_name} is None: raise ValueError(\"Body field '{py_name}' is required.\")")

                lines_rb.append(f"if {py_name} is not None:")
                if is_file and not is_array_of_files:
                    lines_rb.append(f"    files['{openapi_name}'] = {py_name}")
                elif is_file and is_array_of_files:
                    ### ADDED FOR MULTIPLE FILES ###
                    lines_rb.append("    # If it's a list, each item is (filename, fileobj)")
                    lines_rb.append(f"    if isinstance({py_name}, list):")
                    lines_rb.append(f"        for i, single_file in enumerate({py_name}):")
                    lines_rb.append(f"            files[f'{openapi_name}[{{i}}]'] = single_file")
                    lines_rb.append(f"    else:")
                    lines_rb.append(f"        # maybe single-file fallback or raise an error")
                    lines_rb.append(f"        files['{openapi_name}'] = {py_name}")
                else:
                    # text form field
                    lines_rb.append(f"    form_data['{openapi_name}'] = str({py_name})")

            lines_rb.append("if not form_data:")
            lines_rb.append("    form_data = None")
            lines_rb.append("# We'll rename form_data to 'data' so the final call uses data=form_data")
            lines_rb.append("data = form_data")
            data_code = "\n    ".join(lines_rb)
            files_code = "files  # see above"

    lines = []
    lines.append(f"def {func_name}({', '.join(sig_parts)}):")
    lines.append(f"    {docstring}")
    # Insert required param checks:
    for c in required_checks:
        lines.append(f"    {c}")
    lines.append(f"    {endpoint_line}")
    lines.append(f"    {params_code}")

    # Insert request-body required checks if any
    for c in body_required_checks:
        lines.append(f"    {c}")

    lines.append(f"    {data_code}")
    if method.lower() in ['post','put','patch'] and content_type == 'multipart/form-data':
        lines.append("    # files dict might be set above if needed; else None")
        lines.append("    if form_data is None and not files:")
        lines.append("        form_data = None")
        lines.append("    return self.make_request(")
        lines.append(f"        '{method.lower()}',")
        lines.append(f"        endpoint,")
        lines.append("        params=params,")
        lines.append("        data=data,  # form_data / None")
        lines.append("        files=files,")
        lines.append("    )")
    else:
        lines.append("    return self.make_request(")
        lines.append(f"        '{method.lower()}', endpoint, params=params, data=data")
        lines.append("    )")

    lines.append("")
    return "\n".join(lines)

def generate_api_client_from_openapi(openapi_spec_path: str, output_file: str = "generated_client.py"):
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
    lines.append("class SketchEngineClient:")
    lines.append(f"    BASE_URL = \"{base_url}\"")
    lines.append("")
    lines.append("    def __init__(self, api_key=None):")
    lines.append("        self.api_key = api_key or os.environ.get('SKETCH_ENGINE_API_KEY')")
    lines.append("        if not self.api_key:")
    lines.append("            raise ValueError(\"API key must be provided either directly or through SKETCH_ENGINE_API_KEY environment variable\")")
    lines.append("")
    lines.append("        self.session = requests.Session()")
    lines.append("        self.session.headers.update({")
    lines.append("            'Authorization': f'Bearer {self.api_key}'")
    lines.append("        })")
    lines.append("")
    lines.append("    def make_request(self, method, endpoint, params=None, data=None, files=None):")
    lines.append("        \"\"\"")
    lines.append("        Make a request to the Sketch Engine API")
    lines.append("")
    lines.append("        Args:")
    lines.append("            method (str): HTTP method")
    lines.append("            endpoint (str): API endpoint path")
    lines.append("            params (dict, optional): query parameters")
    lines.append("            data (dict or None, optional): JSON or form data")
    lines.append("            files (dict or None, optional): For multipart form-data")
    lines.append("")
    lines.append("        Returns:")
    lines.append("            requests.Response")
    lines.append("        \"\"\"")
    lines.append("        url = f\"{self.BASE_URL}{endpoint}\"")
    lines.append("        try:")
    lines.append("            if files:")
    lines.append("                # multipart form-data likely")
    lines.append("                response = self.session.request(method=method, url=url, params=params, data=data, files=files)")
    lines.append("            else:")
    lines.append("                # normal JSON or query usage")
    lines.append("                if method.upper() in ['POST','PUT','PATCH'] and isinstance(data, dict) and not files:")
    lines.append("                    # We'll guess it's JSON")
    lines.append("                    response = self.session.request(method=method, url=url, params=params, json=data)")
    lines.append("                else:")
    lines.append("                    response = self.session.request(method=method, url=url, params=params, json=data)")
    lines.append("            response.raise_for_status()")
    lines.append("            return response")
    lines.append("        except requests.exceptions.RequestException as e:")
    lines.append("            raise\n")

    paths = spec.get("paths", {})

    # Merge path-level and operation-level parameters carefully
    for path, path_item in paths.items():
        path_params_def = path_item.get('parameters', [])

        for method, method_obj in path_item.items():
            if not isinstance(method_obj, dict):
                continue
            if method.lower() not in ['get','post','put','patch','delete','head','options']:
                continue

            op_params_def = method_obj.get('parameters', [])
            # unify duplicates by (in, name)
            all_params_dict = {}
            for p in (path_params_def + op_params_def):
                p = resolve_ref(p, spec)
                p_in = p.get('in')
                p_name = p.get('name')
                if not p_in or not p_name:
                    continue
                key = (p_in, p_name)
                all_params_dict[key] = p

            all_params = list(all_params_dict.values())

            # separate path vs. query
            path_params_in_spec = []
            query_params_in_spec = []

            for param_def in all_params:
                param_def = resolve_ref(param_def, spec)
                p_in = param_def.get('in','')
                p_name = param_def.get('name','')
                desc = param_def.get('description','')
                required = bool(param_def.get('required', False))
                py_name = sanitize_param_name(p_name)
                if p_in == 'path':
                    path_params_in_spec.append((py_name, p_name, desc, required))
                elif p_in == 'query':
                    query_params_in_spec.append((py_name, p_name, desc, required))

            # requestBody
            ct = get_first_content_type(method_obj)
            rb_fields = parse_request_body_fields(method_obj, spec)

            func_name = generate_function_name(method, path)
            code = build_function_code(
                func_name = func_name,
                method = method,
                path = path,
                path_params_in_spec = path_params_in_spec,
                query_params_in_spec = query_params_in_spec,
                request_body_fields = rb_fields,
                content_type = ct,
                root_spec = spec,
                base_url = base_url
            )
            # indent in class
            for line in code.split('\n'):
                lines.append("    " + line)

    with open(output_file, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(lines))

    print(f"Generated {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_sketchengine_api.py openapi.yaml [output_file.py]")
        sys.exit(1)
    openapi_spec_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "generated_client.py"
    generate_api_client_from_openapi(openapi_spec_path, output_file)

if __name__ == "__main__":
    main()
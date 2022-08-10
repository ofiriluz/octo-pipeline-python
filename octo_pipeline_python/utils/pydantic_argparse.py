import argparse
from typing import Any, Dict, List, Optional, Type


class PydanticArgparse:
    @staticmethod
    def __populate_type(prop_type: str, snake_prop_name: str, default: Optional[str],
                        required: bool, parser: argparse.ArgumentParser,
                        prefix: str = "", description: str = "", ignore_keys: Optional[List[str]] = None) -> None:
        if ignore_keys and snake_prop_name in ignore_keys:
            return
        if default:
            required = False
        arg_type: Type = str
        if prop_type == 'string':
            arg_type = str
        elif prop_type == 'integer':
            arg_type = int
        elif prop_type == 'boolean':
            arg_type = bool
        else:
            arg_type = str
        if arg_type == bool:
            parser.add_argument(
                '--' + prefix + snake_prop_name, required=required, action="store_true",
                help=description)
        else:
            parser.add_argument(
                '--' + prefix + snake_prop_name, required=required, type=arg_type,
                help=description)

    @staticmethod
    def __schema_definition_to_argparse(schema: Dict[str, Any], defaults: Optional[Dict[str, str]], definitions: Optional[Dict[str, Any]],
                                        required: Optional[List[str]], prop_name: str, parser: argparse.ArgumentParser,
                                        prefix: str = "", ignore_keys: Optional[List[str]] = None) -> None:
        if not definitions:
            return
        snake_prop_name = prop_name.replace('_', '-')
        def_prop_name = schema['properties'][prop_name]["$ref"].split("/")[2]
        def_prop = definitions[def_prop_name]
        if 'type' not in def_prop.keys():
            return
        prop_type = def_prop['type']
        desc = ''
        if 'description' in def_prop.keys():
            desc = def_prop['description']
        default: Optional[str] = None
        if 'default' in def_prop.keys():
            default = def_prop['default']
        elif defaults and prefix + snake_prop_name in defaults:
            default = defaults[snake_prop_name]
        if prop_type == 'object':
            PydanticArgparse.schema_to_argparse(
                def_prop, parser, defaults, f"{snake_prop_name}.", definitions, required, ignore_keys)
        else:
            is_required = False
            if required and prop_name in required:
                is_required = True
            PydanticArgparse.__populate_type(prop_type, snake_prop_name, default,
                                             is_required, parser, prefix, desc, ignore_keys)

    @staticmethod
    def __schema_allof_to_argparse(schema: Dict[str, Any], defaults: Optional[Dict[str, str]], definitions: Optional[Dict[str, Any]], required: Optional[List[str]], prop_name: str, parser: argparse.ArgumentParser,
                                   prefix: str = "", ignore_keys: Optional[List[str]] = None) -> None:
        snake_prop_name = prop_name.replace('_', '-')
        desc = ''
        default: Optional[str] = None
        if 'default' in schema['properties'][prop_name].keys():
            default = schema['properties'][prop_name]['default']
        elif defaults and prefix + snake_prop_name in defaults.keys():
            default = defaults[snake_prop_name]
        if 'description' in schema['properties'][prop_name].keys():
            desc = schema['properties'][prop_name]['description']
        for item in schema['properties'][prop_name]['allOf']:
            if "$ref" in item.keys() and definitions:
                def_prop_name = item["$ref"].split("/")[2]
                def_prop = definitions[def_prop_name]
                if 'type' not in def_prop.keys():
                    continue
                prop_type = def_prop['type']
                if prop_type == 'object':
                    PydanticArgparse.schema_to_argparse(
                        def_prop, parser, defaults, f"{snake_prop_name}.", definitions, required, ignore_keys)
                else:
                    is_required = False
                    if required and prop_name in required:
                        is_required = True
                    PydanticArgparse.__populate_type(prop_type, snake_prop_name, default,
                                                     is_required, parser, prefix, desc, ignore_keys)
            else:
                if 'type' not in item.keys():
                    continue
                prop_type = item['type']
                if 'default' in item.keys():
                    default = item['default']
                elif defaults and prefix + snake_prop_name in defaults:
                    default = defaults[snake_prop_name]
                if 'description' in item.keys():
                    desc = item['description']
                if prop_type == 'object':
                    PydanticArgparse.schema_to_argparse(
                        item, parser, defaults, f"{snake_prop_name}.", definitions, required, ignore_keys)
                else:
                    is_required = False
                    if required and prop_name in required:
                        is_required = True
                    PydanticArgparse.__populate_type(prop_type, snake_prop_name, default,
                                                     is_required, parser, prefix, desc, ignore_keys)

    @staticmethod
    def schema_to_argparse(schema: Dict[str, Any], parser: argparse.ArgumentParser, defaults: Optional[Dict[str, str]] = None,
                           prefix: str = "", definitions: Optional[Dict[str, Any]] = None, required: Optional[List[str]] = None,
                           ignore_keys: Optional[List[str]] = None) -> None:
        if not definitions and 'definitions' in schema.keys():
            definitions = schema['definitions']
        elif not definitions:
            definitions = {}
        if not required and 'required' in schema.keys():
            required = schema['required']
        elif not required:
            required = []
        for prop_name in schema['properties'].keys():
            snake_prop_name = prop_name.replace('_', '-')
            if "$ref" in schema['properties'][prop_name].keys():
                PydanticArgparse.__schema_definition_to_argparse(
                    schema, defaults, definitions, required, prop_name, parser, prefix, ignore_keys)
                continue
            elif 'allOf' in schema['properties'][prop_name].keys():
                PydanticArgparse.__schema_allof_to_argparse(
                    schema, defaults, definitions, required, prop_name, parser, prefix, ignore_keys)
                continue
            if 'type' not in schema['properties'][prop_name].keys():
                continue
            prop_type = schema['properties'][prop_name]['type']
            desc = ''
            if 'description' in schema['properties'][prop_name].keys():
                desc = schema['properties'][prop_name]['description']
            default = None
            if 'default' in schema['properties'][prop_name].keys():
                default = schema['properties'][prop_name]['default']
            elif defaults and prefix + snake_prop_name in defaults.keys():
                default = defaults[snake_prop_name]
            if prop_type == 'object':
                PydanticArgparse.schema_to_argparse(
                    schema['properties'][prop_name], parser, defaults, f"{snake_prop_name}.",
                    definitions, required, ignore_keys)
            else:
                is_required = False
                if required and prop_name in required:
                    is_required = True
                PydanticArgparse.__populate_type(prop_type, snake_prop_name, default,
                                                 is_required, parser, prefix, desc, ignore_keys)

    @staticmethod
    def __arg_in_schema(arg_key: str, schema: Dict[str, Any], definitions: Optional[Dict[str, Any]], prefix: str = "") -> Optional[str]:
        for prop_name in schema['properties'].keys():
            snake_prop_name = prop_name.replace('-', '_')
            if "$ref" in schema['properties'][prop_name].keys():
                def_prop_name = schema['properties'][prop_name]["$ref"].split(
                    "/")[2]
                def_prop = definitions[def_prop_name]
                if 'type' not in def_prop.keys():
                    continue
                if def_prop['type'] == 'object':
                    if PydanticArgparse.__arg_in_schema(arg_key, def_prop, definitions, prefix + f"{snake_prop_name}."):
                        return def_prop['type']
                if prefix + snake_prop_name == arg_key:
                    return def_prop['type']
            elif "allOf" in schema['properties'][prop_name].keys():
                for item in schema['properties'][prop_name]["allOf"]:
                    if "$ref" in item.keys():
                        def_prop_name = item["$ref"].split("/")[2]
                        def_prop = definitions[def_prop_name]
                        if 'type' not in def_prop.keys():
                            continue
                        if def_prop['type'] == 'object':
                            if PydanticArgparse.__arg_in_schema(arg_key, def_prop, definitions,
                                                                prefix + f"{snake_prop_name}."):
                                return def_prop['type']
                        if prefix + snake_prop_name == arg_key:
                            return def_prop['type']
                    if 'type' in item.keys():
                        if item['type'] == 'object':
                            if PydanticArgparse.__arg_in_schema(arg_key, item, definitions,
                                                                prefix + f"{snake_prop_name}."):
                                return item['type']
                        if prefix + snake_prop_name == arg_key:
                            return item['type']
            elif 'type' in schema['properties'][prop_name].keys():
                if prefix + snake_prop_name == arg_key:
                    return schema['properties'][prop_name]['type']
                if schema['properties'][prop_name]['type'] == 'object':
                    if PydanticArgparse.__arg_in_schema(arg_key, schema['properties'][prop_name], definitions,
                                                        prefix + f"{snake_prop_name}."):
                        return schema['properties'][prop_name]['type']
        return None

    @staticmethod
    def __arg_to_schema(arg_key: str, arg_val: Any, args_map: Dict[str, Any], arg_type: str) -> None:
        if "." in arg_key:
            args = arg_key.split(".")
            key = args[0]
            if key not in args_map.keys() or not args_map[key]:
                args_map[key] = {}
            PydanticArgparse.__arg_to_schema(".".join(args[1:]), arg_val, args_map[key], arg_type)
        elif arg_val:
            if arg_type == 'array':
                if isinstance(arg_val, list):
                    args_map[arg_key] = arg_val
                else:
                    args_map[arg_key] = arg_val.split(',')
            else:
                args_map[arg_key] = arg_val

    @staticmethod
    def argparse_to_schema(schema: Dict[str, Any], args: argparse.Namespace) -> dict:
        args_map: dict = {}
        definitions: Optional[Dict[str, Any]] = None
        if 'definitions' in schema.keys():
            definitions = schema['definitions']
        for arg_key, arg_val in args.__dict__.items():
            arg_type = PydanticArgparse.__arg_in_schema(arg_key, schema, definitions)
            if not arg_type:
                continue
            PydanticArgparse.__arg_to_schema(arg_key, arg_val, args_map, arg_type)
        return args_map

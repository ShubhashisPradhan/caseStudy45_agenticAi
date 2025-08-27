
"""
JSON Example File Validator

This script validates JSON example files that demonstrate function calling in LLM conversations.
The validator ensures that examples follow a consistent structure and quality standards.

## Main Features
- Schema validation against a defined JSON Schema
- Placeholder detection to ensure real values are used instead of placeholders
- Token/variable consistency checking across function calls
- Verification of function call patterns and responses
- Function argument validation against their defined schemas
- System message structure validation
- Hallucination detection to ensure values come from valid sources
- User identifier detection to ensure examples include proper user inputs

## Validation Checks
1. **JSON Schema**: Validates overall structure against schema.json
2. **Placeholder Detection**: Ensures no placeholder values (YOUR_TOKEN, etc.) are used
3. **Token Consistency**: Checks that token values remain consistent within contexts
4. **Parameter Flow Tracking**: Tracks function input/output parameters and verifies that input parameters come from valid sources (previous function outputs, system message, or user input)
5. **Context Awareness**: Identifies related function calls and ensures parameters
   are consistent within the proper scope
6. **System Message Structure**: Confirms system message follows required format
7. **Function Calls**: Verifies each function call has function output in proper sequence
8. **Function Arguments**: Ensures function call arguments match the defined schema
9. **JSON Response Validation**: Validates function responses are proper JSON
10. **Hallucination Detection**: Verifies that values originate from valid sources (system message, user input, or previous function outputs)
11. **User Identifier Check**: Ensures user messages contain necessary identifiers or references when required
12. **Function Call Breakdown**: Creates a breakdown of function calls for CSV storage

## Usage
Run this script from the command line:
```
python check_all_examples.py
```

By default, it checks all JSON files in the current directory.

### Command Line Options:
- `--show-parameter-flow` or `-p`: Show detailed parameter flow summary for all files (useful for debugging)

Example:
```
python check_all_examples.py --show-parameter-flow
```
"""

import json
import os
import re
import pandas as pd
import datetime
from jsonschema import validate
from jsonschema.exceptions import ValidationError

def validate_json_file(file_path, schema):
    """Validate a single JSON file against the schema and check its structure."""
    print(f"\nChecking file: {file_path}")
    print("=" * 50)

    # Create a result dictionary to track validation outcomes
    results = {
        'file_path': file_path,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'schema_validation': 'Pass',
        'placeholder_check': 'Pass',
        'token_consistency': 'Pass',
        'parameter_flow_check': 'Pass',
        'hallucination_check': 'Pass',
        'user_identifier_check': 'Pass',
        'system_message_validation': 'Pass',
        'function_validation': 'Pass',
        'message_structure': 'Pass',
        'total_function_calls': 0,
        'unique_functions_called': 0,
        'function_call_breakdown': '',
        'errors': []
    }

    # Track overall validation status
    overall_valid = True

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format: {e}"
        print(f"❌ {error_msg}")
        results['schema_validation'] = 'Fail'
        results['errors'].append(error_msg)
        return False, results

    # Validate against schema
    try:
        validate(instance=data, schema=schema)
        print("✅ Schema validation passed")
    except ValidationError as e:
        error_msg = f"Schema validation failed: {e.message} at {' -> '.join([str(p) for p in e.path])}"
        print("❌ Schema validation failed:")
        print(f"  At: {' -> '.join([str(p) for p in e.path])}")
        print(f"  Error: {e.message}")
        results['schema_validation'] = 'Fail'
        results['errors'].append(error_msg)
        overall_valid = False

    # Check for placeholder values in function call arguments
    placeholder_check_result = check_for_placeholders(data)
    if not placeholder_check_result['valid']:
        print("❌ Placeholder values detected in function calls:")
        for issue in placeholder_check_result['issues']:
            print(f"  {issue}")
            results['errors'].append(f"Placeholder check: {issue}")
        results['placeholder_check'] = 'Fail'
        overall_valid = False
    else:
        print("✅ No placeholder values detected in function calls")

    # Check for token/variable consistency across function calls
    consistency_check_result = check_token_consistency(data)
    if not consistency_check_result['valid']:
        print("❌ Inconsistent token/variable values detected:")
        for issue in consistency_check_result['issues']:
            print(f"  {issue}")
            results['errors'].append(f"Token consistency: {issue}")
        results['token_consistency'] = 'Fail'
        overall_valid = False
    else:
        print("✅ All token/variable values are consistent across function calls")

    # Check parameter flow - ensure input parameters come from valid sources
    parameter_flow_check_result = check_parameter_flow(data)
    if not parameter_flow_check_result['valid']:
        print("❌ Parameter flow issues detected:")
        for issue in parameter_flow_check_result['issues']:
            print(f"  {issue}")
            results['errors'].append(f"Parameter flow: {issue}")
        results['parameter_flow_check'] = 'Fail'
        overall_valid = False

        # Print detailed parameter flow summary for debugging
        if parameter_flow_check_result['tracking_data']:
            print_parameter_flow_summary(parameter_flow_check_result['tracking_data'])
    else:
        print("✅ All function input parameters have valid sources")

    # Check for hallucinated values in function calls
    hallucination_check_result = check_for_hallucinations(data)
    if not hallucination_check_result['valid']:
        print("❌ Potential hallucinated values detected:")
        for issue in hallucination_check_result['issues']:
            print(f"  {issue}")
            results['errors'].append(f"Hallucination: {issue}")
        results['hallucination_check'] = 'Fail'
        overall_valid = False
    else:
        print("✅ No hallucinated values detected - all values come from valid sources")

    # Check for user identifiers in messages where they should be present
    user_identifier_check_result = check_user_identifiers(data)
    if not user_identifier_check_result['valid']:
        print("❌ Missing user identifiers or references:")
        for issue in user_identifier_check_result['issues']:
            print(f"  {issue}")
            results['errors'].append(f"User identifiers: {issue}")
        results['user_identifier_check'] = 'Fail'
        overall_valid = False
    else:
        print("✅ User messages contain necessary identifiers where appropriate")

    # Continue with system message validation even if previous checks failed
    system_message_valid = True

    # Check message structure
    if data["messages"][0]["role"] != "system":
        error_msg = "First message is not a system message"
        print(f"❌ {error_msg}")
        results['system_message_validation'] = 'Fail'
        results['errors'].append(error_msg)
        system_message_valid = False
        overall_valid = False

    if not data["messages"][0]["content"].strip().startswith("**Objective**"):
        error_msg = "System message does not start with '**Objective**'"
        print(f"❌ {error_msg}")
        results['system_message_validation'] = 'Fail'
        results['errors'].append(error_msg)
        system_message_valid = False
        overall_valid = False

    if "**Guidelines**" not in data["messages"][0]["content"]:
        error_msg = "System message does not contain '**Guidelines**'"
        print(f"❌ {error_msg}")
        results['system_message_validation'] = 'Fail'
        results['errors'].append(error_msg)
        system_message_valid = False
        overall_valid = False

    if "**Available Tools**" not in data["messages"][0]["content"]:
        error_msg = "System message does not contain '**Available Tools**'"
        print(f"❌ {error_msg}")
        results['system_message_validation'] = 'Fail'
        results['errors'].append(error_msg)
        system_message_valid = False
        overall_valid = False

    if "tools" not in data:
        error_msg = "Tools are missing"
        print(f"❌ {error_msg}")
        results['message_structure'] = 'Fail'
        results['errors'].append(error_msg)
        overall_valid = False

    if data['messages'][-1]['role'] != 'assistant':
        error_msg = "Last message is not an assistant message"
        print(f"❌ {error_msg}")
        results['message_structure'] = 'Fail'
        results['errors'].append(error_msg)
        overall_valid = False

    if system_message_valid:
        print("✅ System message validation passed")

    # Count function calls (do this regardless of previous errors)
    function_calls = {}
    function_responses = {}
    for message in data['messages']:
        if message['role'] == 'assistant' and 'function_call' in message:
            func_name = message['function_call']['name']
            function_calls[func_name] = function_calls.get(func_name, 0) + 1
        elif message['role'] == 'function':
            func_name = message['name']
            function_responses[func_name] = message['content']

    # Print function call statistics
    print("\nFunction Call Statistics:")
    print("-" * 30)
    total_calls = sum(function_calls.values())
    unique_functions = len(function_calls)
    if len(function_calls) < 5:
        print("❌ Need at least 5 unique functions in messages; found {len(unique_functions)}")
        results['function_validation'] = 'Fail'
        results['errors'].append(f"Need at least 5 unique functions in messages; found {len(function_calls)}")
        overall_valid = False

    print(f"Total function calls: {total_calls}")
    print(f"Unique functions called: {unique_functions}")
    print("\nFunction call breakdown:")
    for func_name, count in function_calls.items():
        print(f"  {func_name}: {count} calls")
    print("-" * 30)

    # Store function call statistics in results
    results['total_function_calls'] = total_calls
    results['unique_functions_called'] = unique_functions
    # Create a breakdown string for CSV storage
    breakdown_parts = [f"{func_name}:{count}" for func_name, count in function_calls.items()]
    results['function_call_breakdown'] = "; ".join(breakdown_parts)

    # Validate function calls and descriptions (continue even if previous checks failed)
    function_validation_valid = True

    if 'tools' in data:
        available_function_names = [f['function']['name'] for f in data['tools']]
        available_function_schema = {
            f['function']['name']: f['function']['parameters']
            for f in data['tools']
        }

        # Check function calls and descriptions
        for message in data['messages']:
            if message['role'] == 'assistant' and 'function_call' in message:
                func_name = message['function_call']['name']

                # Check if function exists in tools
                if func_name not in available_function_names:
                    error_msg = f"Function call '{func_name}' is not available in tools"
                    print(f"❌ {error_msg}")
                    results['function_validation'] = 'Fail'
                    results['errors'].append(error_msg)
                    function_validation_valid = False
                    overall_valid = False
                    continue  # Continue checking other functions

                # Validate function arguments
                try:
                    arguments_raw = message['function_call']['arguments']
                    if isinstance(arguments_raw, str):
                        arguments = json.loads(arguments_raw)
                    else:
                        arguments = arguments_raw
                    validate(
                        instance=arguments,
                        schema=available_function_schema[func_name]
                    )
                except ValidationError as e:
                    error_msg = f"Invalid arguments for function '{func_name}': {e.message}"
                    print(f"❌ {error_msg}")
                    results['function_validation'] = 'Fail'
                    results['errors'].append(error_msg)
                    function_validation_valid = False
                    overall_valid = False
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON in function arguments for '{func_name}': {e}"
                    print(f"❌ {error_msg}")
                    results['function_validation'] = 'Fail'
                    results['errors'].append(error_msg)
                    function_validation_valid = False
                    overall_valid = False

                # Check if function response matches description
                if func_name in function_responses:
                    response_content_str = function_responses[func_name]

                    if not isinstance(response_content_str, str):
                        error_msg = f"Function response for '{func_name}' is not a string (type: {type(response_content_str)})"
                        print(f"❌ {error_msg}")
                        results['function_validation'] = 'Fail'
                        results['errors'].append(error_msg)
                        function_validation_valid = False
                        overall_valid = False
                        continue

                    if not response_content_str.strip(): # Check if the string is empty or only whitespace
                        error_msg = f"Function response for '{func_name}' is an empty or whitespace-only string, which is not valid JSON"
                        print(f"❌ {error_msg}")
                        results['function_validation'] = 'Fail'
                        results['errors'].append(error_msg)
                        function_validation_valid = False
                        overall_valid = False
                        continue

                    try:
                        # The 'response' variable is not used later, but parsing it serves as validation.
                        # If it needs to be used, ensure subsequent code uses it.
                        json.loads(response_content_str)
                        # print(f"✅ Function response for '{func_name}' is valid JSON.") # Optional: for verbose success
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON in function response for '{func_name}': {e}"
                        print(f"❌ {error_msg}")
                        max_len = 100
                        problem_str_preview = response_content_str[:max_len]
                        if len(response_content_str) > max_len:
                            problem_str_preview += "..."
                        print(f"  Content that failed to parse: '{problem_str_preview}'")
                        results['function_validation'] = 'Fail'
                        results['errors'].append(error_msg)
                        function_validation_valid = False
                        overall_valid = False

        if function_validation_valid:
            print("✅ Function validation passed")

    # Check CoT messages and function results (continue even if previous checks failed)
    message_structure_valid = True

    for i, message in enumerate(data["messages"]):
        if message["role"] == "assistant" and "function_call" in message:
            # Check CoT message before function call
            if i > 0:  # Make sure there's a previous message
                prev_message = data["messages"][i-1]
                if prev_message["role"] != "cot":
                    error_msg = f"Function call for '{message['function_call']['name']}' not preceded by CoT message"
                    print(f"❌ {error_msg}")
                    results['message_structure'] = 'Fail'
                    results['errors'].append(error_msg)
                    message_structure_valid = False
                    overall_valid = False

            # Check function result after function call
            func_name = message["function_call"]["name"].strip()
            if i + 1 < len(data["messages"]):  # Make sure there's a next message
                next_message = data["messages"][i+1]
                if next_message["role"] != "function" or next_message["name"] != func_name:
                    error_msg = f"Function call for '{func_name}' not followed by proper function result"
                    print(f"❌ {error_msg}")
                    results['message_structure'] = 'Fail'
                    results['errors'].append(error_msg)
                    message_structure_valid = False
                    overall_valid = False
            else:
                error_msg = f"Function call for '{func_name}' is the last message (no function result follows)"
                print(f"❌ {error_msg}")
                results['message_structure'] = 'Fail'
                results['errors'].append(error_msg)
                message_structure_valid = False
                overall_valid = False

    if message_structure_valid:
        print("✅ Message structure validation passed")

    if overall_valid:
        print("✅ All validations passed")
    else:
        print(f"❌ Validation completed with {len(results['errors'])} error(s)")

    return overall_valid, results

def check_user_identifiers(data):
    """Check if user messages contain necessary identifiers or references where appropriate.

    This function only flags missing identifiers if they are not available from function outputs
    or system messages, focusing on identifiers that should come from user input.

    Returns:
        dict: {'valid': bool, 'issues': list of issues}
    """
    result = {'valid': True, 'issues': []}

    # Get parameter tracking data to understand parameter flow
    tracking_data = track_function_parameters(data)

    # Extract function parameter information to know what kinds of IDs might be needed
    id_param_patterns = [
        r'(.+)_id$',        # something_id
        r'(.+)id$',         # somethingid (but not 'id' itself)
        r'^id_(.+)$',       # id_something
    ]
    compiled_id_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in id_param_patterns]

    # Look at what is actually used in function calls and check if they have valid sources
    used_id_params_without_sources = set()

    for message_idx, call_info in tracking_data['parameter_flow'].items():
        func_name = call_info['function_name']

        # Check each parameter in this function call
        for param_name in call_info['input_parameters']:
            # Check if this is an ID parameter
            for pattern in compiled_id_patterns:
                match = pattern.match(param_name)
                if match:
                    entity_type = match.group(1).lower()

                    # Skip very generic entity types and single character matches
                    if (entity_type in ('parameter', 'type', 'input', 'output', 'arg', 'argument', 'prop', 'property') or
                        len(entity_type) <= 1):
                        continue

                    # Check if this parameter has a valid source
                    if param_name in call_info['untracked_parameters']:
                        # This parameter doesn't have a traceable source
                        # Only flag it if it's not a system-level identifier that should come from user input

                        # Skip parameters that are typically generated or come from system configuration
                        system_generated_types = {
                            'session', 'recording', 'assignment', 'document', 'file', 'event', 'meeting',
                            'notification', 'message', 'announcement', 'calendar', 'task', 'job', 'process'
                        }

                        if entity_type not in system_generated_types:
                            used_id_params_without_sources.add(entity_type)

                    break

    # Extract user messages to check for IDs
    user_messages = [m for m in data['messages'] if m['role'] == 'user']
    if len(user_messages) == 0:
        # No user messages to check
        return result

    # Check if any ID patterns appear in user messages
    id_matches_in_user = {}

    for entity_type in used_id_params_without_sources:
        # Different patterns for how this entity might appear in text
        patterns = [
            rf"\b{entity_type}\s*(?:id|identifier)?\s*[:#]?\s*([A-Za-z0-9_\-\.]+)\b",  # user_id: ABC123
            rf"\b(?:id|identifier)?\s*(?:of|for)?\s*{entity_type}\s*[:#]?\s*([A-Za-z0-9_\-\.]+)\b",  # id for user: ABC123
            rf"\b([A-Za-z0-9_\-\.]+)\s*(?:as|is|for)?\s*(?:the)?\s*{entity_type}\s*(?:id|identifier)?\b",  # ABC123 as the user id
            rf"\b{entity_type}\s*(?:is|=)\s*([A-Za-z0-9_\-\.]+)\b"  # user = ABC123
        ]

        found_match = False
        for user_message in user_messages:
            message_text = user_message['content']

            for pattern in patterns:
                matches = re.findall(pattern, message_text, re.IGNORECASE)
                if matches:
                    id_matches_in_user[entity_type] = matches[0]
                    found_match = True
                    break

            if found_match:
                break

        if not found_match:
            # Look for entities that might be at the end of the message
            for user_message in user_messages:
                message_text = user_message['content']

                # Look for simple ID-like values at end of sentences
                end_patterns = [
                    rf"[\.\s]([A-Z0-9]{{3,}})[\.!]?$",  # ABC123
                    rf"[\.\s]([A-Z]{{2,}}[_\-][0-9]{{2,}})[\.!]?$",  # MATH-101
                ]

                for pattern in end_patterns:
                    matches = re.findall(pattern, message_text)
                    if matches:
                        id_matches_in_user[entity_type] = matches[0]
                        found_match = True
                        break

                if found_match:
                    break

    # Report any missing IDs that should come from user input
    for entity_type in used_id_params_without_sources:
        if entity_type not in id_matches_in_user:
            result['valid'] = False
            result['issues'].append(
                f"Function calls use '{entity_type}_id' but no user message provides a {entity_type} identifier"
            )

    return result

def track_function_parameters(data):
    """Track function input and output parameters to verify parameter flow.

    Returns:
        dict: {
            'parameter_flow': dict mapping function calls to their parameter sources,
            'function_outputs': dict of all function outputs by message index,
            'parameter_tracking': dict tracking where each parameter value comes from
        }
    """
    tracking_result = {
        'parameter_flow': {},
        'function_outputs': {},
        'parameter_tracking': {},
        'issues': []
    }

    # Track all function outputs first
    for i, message in enumerate(data['messages']):
        if message['role'] == 'function':
            func_name = message['name']
            try:
                output_raw = message['content']
                if isinstance(output_raw, str):
                    output = json.loads(output_raw)
                else:
                    output = output_raw
                tracking_result['function_outputs'][i] = {
                    'function_name': func_name,
                    'output': output,
                    'message_index': i
                }

                # Extract all output parameters recursively
                def extract_output_params(obj, path=""):
                    params = {}
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            current_path = f"{path}.{key}" if path else key
                            if isinstance(value, (str, int, float, bool)) and value is not None:
                                params[current_path] = {
                                    'value': value,
                                    'type': type(value).__name__,
                                    'source_function': func_name,
                                    'source_message': i
                                }
                            elif isinstance(value, (dict, list)):
                                params.update(extract_output_params(value, current_path))
                    elif isinstance(obj, list):
                        for idx, item in enumerate(obj):
                            current_path = f"{path}[{idx}]" if path else f"[{idx}]"
                            if isinstance(item, (str, int, float, bool)) and item is not None:
                                params[current_path] = {
                                    'value': item,
                                    'type': type(item).__name__,
                                    'source_function': func_name,
                                    'source_message': i
                                }
                            elif isinstance(item, (dict, list)):
                                params.update(extract_output_params(item, current_path))
                    return params

                output_params = extract_output_params(output)
                tracking_result['parameter_tracking'].update(output_params)

            except json.JSONDecodeError:
                tracking_result['issues'].append(f"Could not parse function output for '{func_name}' at message {i}")

    # Now track function inputs and their sources
    for i, message in enumerate(data['messages']):
        if message['role'] == 'assistant' and 'function_call' in message:
            func_name = message['function_call']['name']
            try:
                # Handle both string and dict arguments
                arguments_raw = message['function_call']['arguments']
                if isinstance(arguments_raw, str):
                    arguments = json.loads(arguments_raw)
                else:
                    arguments = arguments_raw

                call_tracking = {
                    'function_name': func_name,
                    'message_index': i,
                    'input_parameters': {},
                    'parameter_sources': {},
                    'untracked_parameters': []
                }

                # Check each input parameter
                for param_name, param_value in arguments.items():
                    if isinstance(param_value, (str, int, float, bool)):
                        call_tracking['input_parameters'][param_name] = {
                            'value': param_value,
                            'type': type(param_value).__name__
                        }

                        # Find source of this parameter value
                        found_source = False
                        param_value_str = str(param_value)

                        # Check if this value comes from previous function outputs
                        for param_path, param_info in tracking_result['parameter_tracking'].items():
                            if str(param_info['value']) == param_value_str and param_info['source_message'] < i:
                                call_tracking['parameter_sources'][param_name] = {
                                    'source_type': 'function_output',
                                    'source_function': param_info['source_function'],
                                    'source_message': param_info['source_message'],
                                    'source_parameter': param_path
                                }
                                found_source = True
                                break

                        # Check if this value comes from system message
                        if not found_source:
                            system_message = data["messages"][0]["content"]
                            if param_value_str in system_message:
                                call_tracking['parameter_sources'][param_name] = {
                                    'source_type': 'system_message',
                                    'source_function': None,
                                    'source_message': 0,
                                    'source_parameter': 'system_content'
                                }
                                found_source = True

                        # Check if this value comes from user messages
                        if not found_source:
                            for msg_idx, msg in enumerate(data['messages']):
                                if msg['role'] == 'user' and param_value_str in msg['content']:
                                    call_tracking['parameter_sources'][param_name] = {
                                        'source_type': 'user_input',
                                        'source_function': None,
                                        'source_message': msg_idx,
                                        'source_parameter': 'user_content'
                                    }
                                    found_source = True
                                    break

                        if not found_source:
                            call_tracking['untracked_parameters'].append(param_name)

                tracking_result['parameter_flow'][i] = call_tracking

            except json.JSONDecodeError:
                tracking_result['issues'].append(f"Could not parse function arguments for '{func_name}' at message {i}")

    return tracking_result

def check_parameter_flow(data):
    """Check if function input parameters come from valid sources (previous outputs, system message, or user input).

    Returns:
        dict: {'valid': bool, 'issues': list of issues, 'tracking_data': tracking information}
    """
    result = {'valid': True, 'issues': [], 'tracking_data': None}

    # Get parameter tracking data
    tracking_data = track_function_parameters(data)
    result['tracking_data'] = tracking_data

    # Add any tracking issues
    if tracking_data['issues']:
        result['issues'].extend(tracking_data['issues'])
        result['valid'] = False

    # Parameters that are expected to be generated or hardcoded (not from previous outputs)
    expected_generated_params = {
        'top_p', 'stop', 'best_of', 'prompt', 'text', 'message'
    }

    # Check each function call for parameter flow issues
    for msg_idx, call_info in tracking_data['parameter_flow'].items():
        func_name = call_info['function_name']

        # Check for untracked parameters that should have sources
        for param_name in call_info['untracked_parameters']:
            # Skip parameters that are expected to be generated/hardcoded
            if param_name.lower() in expected_generated_params:
                continue

            # Skip very short values that might be flags or simple settings
            param_value = call_info['input_parameters'][param_name]['value']
            if isinstance(param_value, (bool, int)) and isinstance(param_value, bool):
                continue
            if isinstance(param_value, int) and param_value < 1000:
                continue
            if isinstance(param_value, str) and len(param_value) < 5:
                continue

            result['valid'] = False
            result['issues'].append(
                f"Parameter '{param_name}' in function '{func_name}' (message {msg_idx}) "
                f"with value '{param_value}' has no traceable source from previous outputs, "
                f"system message, or user input"
            )

    return result

def print_parameter_flow_summary(tracking_data):
    """Print a summary of parameter flow for debugging purposes."""
    print("\nParameter Flow Summary:")
    print("-" * 50)

    print(f"Total function outputs tracked: {len(tracking_data['function_outputs'])}")
    print(f"Total function calls tracked: {len(tracking_data['parameter_flow'])}")
    print(f"Total output parameters tracked: {len(tracking_data['parameter_tracking'])}")

    print("\nFunction Call Parameter Sources:")
    for msg_idx, call_info in tracking_data['parameter_flow'].items():
        func_name = call_info['function_name']
        print(f"\n  {func_name} (message {msg_idx}):")

        for param_name, source_info in call_info['parameter_sources'].items():
            source_type = source_info['source_type']
            if source_type == 'function_output':
                print(f"    {param_name}: from {source_info['source_function']} output ({source_info['source_parameter']})")
            elif source_type == 'system_message':
                print(f"    {param_name}: from system message")
            elif source_type == 'user_input':
                print(f"    {param_name}: from user input (message {source_info['source_message']})")

        if call_info['untracked_parameters']:
            print(f"    Untracked parameters: {', '.join(call_info['untracked_parameters'])}")

    print("-" * 50)

def check_for_hallucinations(data):
    """Check if function call values come from valid sources (system message, user input, or previous function outputs).

    Returns:
        dict: {'valid': bool, 'issues': list of issues}
    """
    result = {'valid': True, 'issues': []}

    # Use the new parameter tracking system
    tracking_data = track_function_parameters(data)

    # Add any tracking issues to the result
    if tracking_data['issues']:
        result['issues'].extend(tracking_data['issues'])

    # Extract all potential sources of values
    value_sources = {}

    # 1. System message - extract tokens and other defined values
    system_message = data["messages"][0]["content"]

    # Extract tokens and their values from the API Keys and Tokens section
    api_section_match = re.search(r"\*\*API Keys and Tokens\*\*:\s*\n(.*?)(?=\n\*\*|$)", system_message, re.DOTALL)

    if api_section_match:
        api_section = api_section_match.group(1)
        # Extract tokens from the API section
        token_pattern = re.compile(r"- ([A-Za-z0-9_ ]+)(?:Token|API Key|JWT|OAuth|Bearer|Key|Secret): ([A-Za-z0-9_\.\-\s]+)", re.IGNORECASE)
        token_matches = token_pattern.findall(api_section)

        for token_name, token_value in token_matches:
            # Handle Bearer tokens properly
            token_value = token_value.strip()
            value_sources[token_value] = f"system message token ({token_name})"

            # If it's a Bearer token, also add the token part without "Bearer "
            if token_value.startswith('Bearer '):
                raw_token = token_value[7:]
                value_sources[raw_token] = f"system message token ({token_name} - raw)"

    # Also check the entire system message for any other values
    # Extract model names, tool names, and other configuration values
    model_pattern = re.compile(r"model\s*:\s*([a-zA-Z0-9\-_]+)", re.IGNORECASE)
    model_matches = model_pattern.findall(system_message)
    for model in model_matches:
        value_sources[model] = "system message (model)"

    # Extract tool names from the Available tools section
    tools_pattern = re.compile(r"\*\*Available tools\*\*:\s*([^.]+)", re.IGNORECASE)
    tools_match = tools_pattern.search(system_message)
    if tools_match:
        tools_text = tools_match.group(1)
        tool_names = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)", tools_text)
        for tool_name in tool_names:
            value_sources[tool_name] = "system message (available tool)"

    # 2. User messages - extract potential values
    for i, message in enumerate(data['messages']):
        if message['role'] == 'user':
            user_content = message['content']

            # Extract all potential values from user messages using multiple strategies

            # Add the entire user content as a searchable source for substring matching
            value_sources[f"__USER_MESSAGE_{i}__"] = f"user message {i} (full content)"

            # Strategy 1: Extract quoted strings (values in quotes)
            quoted_pattern = re.compile(r'["\']([^"\']+)["\']')
            quoted_matches = quoted_pattern.findall(user_content)
            for quoted_value in quoted_matches:
                if quoted_value not in value_sources:
                    value_sources[quoted_value] = f"user message {i} (quoted)"

            # Strategy 2: Extract common identifiers and values
            # Course IDs like MATH101, CS101, etc.
            course_id_pattern = re.compile(r'\b([A-Z]{2,}[0-9]{2,})\b')
            course_id_matches = course_id_pattern.findall(user_content)
            for course_id in course_id_matches:
                if course_id not in value_sources:
                    value_sources[course_id] = f"user message {i} (course ID)"

            # Email addresses
            email_pattern = re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b')
            email_matches = email_pattern.findall(user_content)
            for email in email_matches:
                if email not in value_sources:
                    value_sources[email] = f"user message {i} (email)"

            # Dates in various formats
            date_patterns = [
                r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',  # May 1, 2025
                r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # 5/1/2025
                r'\b(\d{4}-\d{2}-\d{2})\b',      # 2025-05-01
                r'\b(\d{1,2}-\d{1,2}-\d{4})\b'   # 5-1-2025
            ]
            for date_pattern in date_patterns:
                date_matches = re.findall(date_pattern, user_content, re.IGNORECASE)
                for date_match in date_matches:
                    if date_match not in value_sources:
                        value_sources[date_match] = f"user message {i} (date)"

            # Times in various formats
            time_patterns = [
                r'\b(\d{1,2}:\d{2}\s*(?:AM|PM))\b',  # 10:00 AM, 11:30 PM
                r'\b(\d{1,2}:\d{2}:\d{2})\b',        # 10:00:00
                r'\b(\d{1,2}:\d{2})\b'               # 10:00
            ]
            for time_pattern in time_patterns:
                time_matches = re.findall(time_pattern, user_content, re.IGNORECASE)
                for time_match in time_matches:
                    if time_match not in value_sources:
                        value_sources[time_match] = f"user message {i} (time)"

            # Timezone abbreviations
            timezone_pattern = re.compile(r'\b(UTC|EST|PST|CST|MST|GMT|EDT|PDT|CDT|MDT)\b')
            timezone_matches = timezone_pattern.findall(user_content)
            for timezone in timezone_matches:
                if timezone not in value_sources:
                    value_sources[timezone] = f"user message {i} (timezone)"

            # Numbers (durations, amounts, etc.)
            number_pattern = re.compile(r'\b(\d+)\s*(?:minutes?|hours?|days?|mins?|hrs?)\b')
            number_matches = number_pattern.findall(user_content)
            for number in number_matches:
                if number not in value_sources:
                    value_sources[number] = f"user message {i} (duration)"

            # Standalone numbers that might be important
            standalone_number_pattern = re.compile(r'\b(\d{2,})\b')
            standalone_numbers = standalone_number_pattern.findall(user_content)
            for number in standalone_numbers:
                if number not in value_sources and len(number) >= 2:
                    value_sources[number] = f"user message {i} (number)"

            # Common exam/course related terms
            exam_terms = re.findall(r'\b(Final\s+Exam|Midterm\s+Exam|Quiz\s+\d+|Test\s+\d+|Assignment\s+\d+)\b', user_content, re.IGNORECASE)
            for term in exam_terms:
                if term not in value_sources:
                    value_sources[term] = f"user message {i} (exam term)"

            # Generic alphanumeric identifiers (6+ chars)
            id_pattern = re.compile(r'\b([A-Za-z0-9_\.\-]{6,})\b')
            id_matches = id_pattern.findall(user_content)
            for potential_id in id_matches:
                if potential_id not in value_sources:
                    value_sources[potential_id] = f"user message {i} (identifier)"

            # Extract any words that might be names or titles (capitalized words)
            name_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')
            name_matches = name_pattern.findall(user_content)
            for name in name_matches:
                # Skip very common words
                if name.lower() not in ['the', 'and', 'for', 'with', 'from', 'that', 'this', 'schedule', 'arrange', 'exam', 'test', 'course', 'student', 'students']:
                    if name not in value_sources:
                        value_sources[name] = f"user message {i} (name/title)"

            # Extract individual words that might be referenced in prompts
            words = re.findall(r'\b([A-Za-z0-9]+)\b', user_content)
            for word in words:
                if len(word) >= 3 and word not in value_sources:  # Only words 3+ chars
                    value_sources[word] = f"user message {i} (word)"

    # 3. Function outputs - extract all values from function outputs recursively
    func_outputs = {}

    def extract_values_recursively(obj, path="", func_name="", message_idx=0):
        """Recursively extract all values from a nested object/array structure."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, (str, int, float, bool)) and value is not None:
                    value_str = str(value)
                    if value_str not in value_sources:
                        value_sources[value_str] = f"function output from {func_name} (key: {current_path})"
                elif isinstance(value, (dict, list)):
                    extract_values_recursively(value, current_path, func_name, message_idx)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                current_path = f"{path}[{idx}]" if path else f"[{idx}]"
                if isinstance(item, (str, int, float, bool)) and item is not None:
                    value_str = str(item)
                    if value_str not in value_sources:
                        value_sources[value_str] = f"function output from {func_name} (array item: {current_path})"
                elif isinstance(item, (dict, list)):
                    extract_values_recursively(item, current_path, func_name, message_idx)
        elif isinstance(obj, (str, int, float, bool)) and obj is not None:
            value_str = str(obj)
            if value_str not in value_sources:
                value_sources[value_str] = f"function output from {func_name} (direct value)"

    for i, message in enumerate(data['messages']):
        if message['role'] == 'function':
            func_name = message['name']
            try:
                output = json.loads(message['content'])
                func_outputs[i] = {
                    'name': func_name,
                    'output': output
                }

                # Extract all values recursively from the function output
                extract_values_recursively(output, "", func_name, i)

            except json.JSONDecodeError:
                continue  # Skip invalid JSON

    # Parameters that are expected to contain generated content
    text_content_params = {
        # Email-related content
        'body', 'email_body', 'html_body', 'text_body', 'content', 'message_body',
        'email_content', 'mail_body', 'body_text', 'body_html',

        # Message-related content
        'message', 'text', 'message_text', 'notification_text',
        'sms_text', 'whatsapp_message', 'telegram_message',

        # HTML/UI content
        'html', 'html_content', 'markup', 'template', 'description', 'rich_text',

        # Other common content fields
        'summary', 'comment', 'note', 'post', 'caption', 'announcement',
        'feedback', 'review', 'response', 'reply'
    }


    # Now check function call arguments for values that don't come from any known source
    for i, message in enumerate(data['messages']):
        if message['role'] == 'assistant' and 'function_call' in message:
            func_name = message['function_call']['name']
            try:
                arguments_raw = message['function_call']['arguments']
                if isinstance(arguments_raw, str):
                    arguments = json.loads(arguments_raw)
                else:
                    arguments = arguments_raw

                # Calculate which previous function outputs are accessible to this function call
                available_outputs = {}
                for output_idx, output_data in func_outputs.items():
                    if output_idx < i:  # Only outputs before this function call
                        available_outputs[output_idx] = output_data

                # Process each argument
                for param_name, param_value in arguments.items():
                    # Skip complex objects
                    if isinstance(param_value, (str, int, float, bool)):
                        param_value_str = str(param_value)
                        normalized_param_name = param_name.lower()

                        # Check if this value comes from a known source
                        if param_value_str not in value_sources:
                            # Additional check: see if this value appears in any previous function output
                            # even if it wasn't captured by our recursive extraction (edge cases)
                            found_in_output = False
                            for output_idx, output_data in available_outputs.items():
                                output_str = json.dumps(output_data['output'])
                                if param_value_str in output_str:
                                    found_in_output = True
                                    # Add this to value_sources for future reference
                                    value_sources[param_value_str] = f"function output from {output_data['name']} (found in output string)"
                                    break

                            if found_in_output:
                                continue

                            # Check if the value appears as a substring in user messages or system message
                            found_in_text = False

                            # Check system message
                            if param_value_str in system_message:
                                found_in_text = True
                                value_sources[param_value_str] = "system message (substring match)"

                            # Check user messages
                            if not found_in_text:
                                for msg_idx, msg in enumerate(data['messages']):
                                    if msg['role'] == 'user' and param_value_str in msg['content']:
                                        found_in_text = True
                                        value_sources[param_value_str] = f"user message {msg_idx} (substring match)"
                                        break

                            # For prompts, check if the content is composed of known elements
                            if not found_in_text and normalized_param_name == 'prompt':
                                # Check if the prompt contains multiple known values/words
                                known_elements = []
                                for known_value, source in value_sources.items():
                                    if not known_value.startswith('__USER_MESSAGE_') and known_value in param_value_str:
                                        known_elements.append(known_value)

                                # If the prompt contains several known elements, it's likely legitimate
                                if len(known_elements) >= 3:
                                    found_in_text = True
                                    value_sources[param_value_str] = f"prompt composed of known elements: {', '.join(known_elements[:3])}..."

                            if found_in_text:
                                continue

                            # Special handling for dates which might be generated
                            if re.match(r'^\d{4}-\d{2}-\d{2}T', param_value_str):
                                continue

                            # Found a potentially hallucinated value
                            result['valid'] = False
                            result['issues'].append(
                                f"Potential hallucinated value '{param_value_str}' in parameter '{param_name}' of function '{func_name}' "
                                f"(message {i}) - value doesn't come from system prompt, user input, or previous function outputs"
                            )
            except json.JSONDecodeError:
                result['valid'] = False
                result['issues'].append(f"Could not parse function arguments for '{func_name}'")

    return result

def check_for_placeholders(data):
    """Check for placeholder values in function call arguments and system prompt.

    Returns:
        dict: {'valid': bool, 'issues': list of issues}
    """
    result = {'valid': True, 'issues': []}

    # Common placeholder patterns
    placeholder_patterns = [
        r"YOUR_[A-Z_]+",  # YOUR_TOKEN, YOUR_API_KEY, etc.
        r"PLACEHOLDER",
        # Modified pattern to avoid matching HTML tags but catch placeholder-style angle brackets
        r"<(?!/?(?:p|div|span|a|br|ul|ol|li|h[1-6]|img|table|tr|td|th|code|pre|button|input|form|strong|em|i|b)[^>]*>)[A-Z_]+>",  # <TOKEN>, <API_KEY>, etc. but not HTML tags
        r"XXX+",       # XXXX, XXXXX, etc.
        r"[A-Z_]+ +HERE",  # TOKEN HERE, API_KEY HERE, etc.
        r"PUT +[A-Z_]+ +HERE",  # PUT TOKEN HERE, etc.
        r"REPLACE_WITH_[A-Z_]+",  # REPLACE_WITH_TOKEN, etc.
        r"\[\[.*?\]\]"  # [[placeholder]]
    ]

    # Compile regex patterns for efficiency
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in placeholder_patterns]

    # Check function calls
    for message in data['messages']:
        if message['role'] == 'assistant' and 'function_call' in message:
            func_name = message['function_call']['name']
            arguments = message['function_call']['arguments']

            # Check each pattern in the arguments
            # Convert arguments to string if it's a dict/object
            arguments_str = json.dumps(arguments) if isinstance(arguments, (dict, list)) else str(arguments)
            for pattern in compiled_patterns:
                matches = pattern.findall(arguments_str)
                if matches:
                    result['valid'] = False
                    result['issues'].append(f"Function '{func_name}' contains placeholder(s): {', '.join(matches)}")

        # Check for placeholders in the system message
        for pattern in compiled_patterns:
            matches = pattern.findall(data['messages'][0]['content'])
            if matches:
                result['valid'] = False
                result['issues'].append(f"System message contains placeholder(s): {', '.join(matches)}")

        # Check for placeholders in the user message
        for pattern in compiled_patterns:
            matches = pattern.findall(data['messages'][1]['content'])
            if matches:
                result['valid'] = False
                result['issues'].append(f"User message contains placeholder(s): {', '.join(matches)}")

    return result

def check_token_consistency(data):
    """Check if token values and variables are consistent across all function calls.

    Returns:
        dict: {'valid': bool, 'issues': list of issues}
    """
    result = {'valid': True, 'issues': []}

    # Extract tokens from system message if available
    token_values = {}
    user_message = data["messages"][1]["content"]

    # Find the "**API Keys and Tokens**" section
    api_section_match = re.search(r"\*\*API Keys and Tokens\*\*:\s*\n(.*?)(?=\n\*\*|$)", user_message, re.DOTALL)

    if api_section_match:
        api_section_text = api_section_match.group(1)
        # Find all tokens in the API section in the pattern of "TOKEN: value"
        tokens = re.findall(r"[\w-]+:\s*[\w-]+", api_section_text)
    else:
        print("Warning : No API section found")
        tokens = []
        result['valid'] = False
        result['issues'].append("No API section found")

    # Check function calls
    for message in data['messages']:
        if message['role'] == 'assistant' and 'function_call' in message:
            func_name = message['function_call']['name']
            arguments = message['function_call']['arguments']
            for argument in arguments:
                if argument in tokens:
                    result['valid'] = False
                    result['issues'].append(f"Function call '{func_name}' contains token '{argument}'")

    return result

def get_json_files(directory='./Batch_5_Submissions'):
    """
    Get all JSON files in the specified directory, excluding 'schema.json'

    Args:
        directory (str): Path to directory to search, defaults to './Batch_5_Submissions'

    Returns:
        list: List of JSON filenames with their full paths
    """
    try:
        # Check if directory exists
        if not os.path.isdir(directory):
            print(f"Directory '{directory}' not found")
            return []

        # Get absolute path of the directory if it's relative
        if not os.path.isabs(directory):
            directory = os.path.abspath(directory)

        excluded_files = ['schema.json', 'tools_dict.json', 'results.json']

        # List all files in the directory with .json extension, excluding schema.json
        json_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.json') and f not in excluded_files]

        return json_files
    except Exception as e:
        print(f"Error listing JSON files: {str(e)}")
        return []

def main():
    import sys
    import argparse
    from  pathlib import Path

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Validate JSON example files for function calling in LLM conversations.')
    parser.add_argument('--data-dir', '-d',
                       default='./out',
                       help='Directory containing JSON files to validate (default: ./out)')
    parser.add_argument('--show-parameter-flow', '-p',
                       action='store_true',
                       help='Show detailed parameter flow summary for all files')

    # Parse arguments
    args = parser.parse_args()

    # Load schema
    try:
        with open(Path('S:\ARTLY\case_study\caseStudy45_agenticAi\out\Case_Study_045_workflow.json'), 'r',encoding='utf-8') as f:
            schema = json.load(f)
    except FileNotFoundError:
        print("❌ schema.json not found")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Invalid schema.json: {e}")
        return

    # Get all JSON files in the specified directory
    json_files = get_json_files(args.data_dir)
    print(f"Found {len(json_files)} files in directory: {args.data_dir}")

    # Sort the json files by the number in the filename if it exists, otherwise by name
    def sort_key(filename):
        try:
            # Try to extract number from filename (e.g., "example5.json" -> 5)
            return int(''.join(filter(str.isdigit, filename)))
        except ValueError:
            # If no number found, use the filename itself
            return filename

    json_files.sort(key=sort_key)

    if not json_files:
        print("No JSON files found in current directory")
        return

    print(f"Found {len(json_files)} JSON files to check")

    # Create a DataFrame to store results
    results_df = pd.DataFrame(columns=[
        'file_path', 'timestamp', 'schema_validation', 'placeholder_check',
        'token_consistency', 'parameter_flow_check', 'hallucination_check', 'user_identifier_check',
        'system_message_validation', 'function_validation', 'message_structure',
        'total_function_calls', 'unique_functions_called', 'function_call_breakdown',
        'errors'
    ])

    # Validate each file
    all_valid = True
    for json_file in json_files:
        is_valid, result_dict = validate_json_file(json_file, schema)
        if not is_valid:
            all_valid = False

        # Show parameter flow summary if requested
        if args.show_parameter_flow:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                tracking_data = track_function_parameters(data)
                print_parameter_flow_summary(tracking_data)
            except Exception as e:
                print(f"Could not generate parameter flow summary for {json_file}: {e}")

        # Add results to DataFrame
        results_df = pd.concat([results_df, pd.DataFrame([result_dict])], ignore_index=True)

    if all_valid:
        print("\n✅ All files passed validation")
    else:
        print("\n❌ Some files failed validation")

    # Save results to CSV file
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"validation_results_{timestamp}.csv"
    results_df.to_csv(csv_filename, index=False)
    print(f"\nResults saved to {csv_filename}")

if __name__ == "__main__":
    main()


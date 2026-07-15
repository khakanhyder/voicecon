# Data Mapper Guide

Complete guide to the Voicecon Data Mapping Engine.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Concepts](#core-concepts)
4. [API Reference](#api-reference)
5. [Mapping Configuration](#mapping-configuration)
6. [Transformations](#transformations)
7. [Validation](#validation)
8. [Integration with Workflows](#integration-with-workflows)
9. [Advanced Usage](#advanced-usage)
10. [Best Practices](#best-practices)

---

## Overview

The Data Mapping Engine is a powerful and flexible system for transforming data between different formats and structures. It's designed to work seamlessly with the Voicecon workflow system and integration connectors.

### Key Features

- **Field Mapping**: Map fields from source to target with dot notation support
- **Transformations**: 30+ built-in transformations for strings, numbers, dates, and arrays
- **Templates**: Combine multiple fields using `{{variable}}` syntax
- **Formulas**: Perform calculations using safe expression evaluation
- **Validation**: Comprehensive validation with type checking and pattern matching
- **Nested Objects**: Deep nested object support with array indexing
- **Chaining**: Chain multiple transformations sequentially
- **Post-Processing**: Remove nulls, flatten objects, and more

### Use Cases

1. **Integration Mapping**: Transform data between different CRM/integration formats
2. **API Response Transformation**: Reshape API responses for consumption
3. **Data Normalization**: Standardize data from multiple sources
4. **Report Generation**: Format data for reports and notifications
5. **Workflow Data Processing**: Transform data between workflow steps

---

## Architecture

### Components

```
DataMapper (Singleton)
├── map_fields()           # Main entry point
├── apply_transformation() # Apply single transformation
├── _get_nested_value()    # Extract nested values
├── _set_nested_value()    # Set nested values
├── _apply_template()      # Template rendering
├── _apply_formula()       # Formula evaluation
├── _validate_output()     # Data validation
└── transformations{}      # 30+ transformation functions
```

### File Structure

```
backend/app/services/workflows/
├── data_mapper.py              # Core DataMapper implementation
├── step_handlers.py            # TransformStepHandler integration
└── __init__.py                 # Exports
```

### Integration Points

1. **Workflow Transform Steps**: Used in transform step handlers
2. **API Endpoints**: Can be used directly in endpoint logic
3. **Background Jobs**: Transform data in async tasks
4. **Integration Connectors**: Map data between integration formats

---

## Core Concepts

### 1. Field Mapping

Map fields from source data to target structure:

```python
mapping_config = {
    "fields": {
        "target_field": "source_field",
        "email": "contact.email",
        "name": "contact.name"
    }
}
```

### 2. Dot Notation

Access nested fields using dots:

```python
"user.address.city"  # Access: data["user"]["address"]["city"]
"items[0].name"      # Access: data["items"][0]["name"]
```

### 3. Transformations

Apply transformations to values:

```python
{
    "uppercase_email": {
        "source": "email",
        "transform": "uppercase"
    }
}
```

### 4. Templates

Combine multiple fields:

```python
{
    "full_name": {
        "template": "{{first_name}} {{last_name}}"
    }
}
```

### 5. Formulas

Perform calculations:

```python
{
    "total": {
        "formula": "price * quantity"
    }
}
```

### 6. Validation

Validate output data:

```python
{
    "validation": {
        "required": ["email"],
        "types": {"email": "string"},
        "patterns": {"email": "^[^@]+@[^@]+\\.[^@]+$"}
    }
}
```

---

## API Reference

### DataMapper Class

#### `map_fields(source_data, mapping_config, validate=True)`

Main entry point for mapping data.

**Parameters:**
- `source_data` (dict): Source data dictionary
- `mapping_config` (dict): Mapping configuration
- `validate` (bool): Whether to validate output (default: True)

**Returns:** dict - Mapped data

**Raises:**
- `DataMappingError`: If mapping fails
- `ValidationError`: If validation fails

**Example:**
```python
from app.services.workflows.data_mapper import get_data_mapper

mapper = get_data_mapper()

source = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "JOHN@EXAMPLE.COM"
}

config = {
    "fields": {
        "name": {
            "template": "{{first_name}} {{last_name}}"
        },
        "email": {
            "source": "email",
            "transform": "lowercase"
        }
    }
}

result = mapper.map_fields(source, config)
# {"name": "John Doe", "email": "john@example.com"}
```

#### `apply_transformation(value, transform_spec)`

Apply a single transformation to a value.

**Parameters:**
- `value` (Any): Value to transform
- `transform_spec` (str | dict): Transformation specification

**Returns:** Any - Transformed value

**Raises:**
- `DataMappingError`: If transformation fails

**Example:**
```python
mapper.apply_transformation("hello world", "uppercase")
# "HELLO WORLD"

mapper.apply_transformation(3.14159, "round:2")
# 3.14

mapper.apply_transformation("hello", ["uppercase", "truncate:3"])
# "HEL..."
```

### Helper Functions

#### `get_data_mapper()`

Get singleton DataMapper instance.

**Returns:** DataMapper

**Example:**
```python
from app.services.workflows.data_mapper import get_data_mapper

mapper = get_data_mapper()
```

---

## Mapping Configuration

### Configuration Structure

```python
{
    "fields": {
        # Field mappings
        "target_field": "source_field" | mapping_spec
    },
    "validation": {
        # Validation rules (optional)
        "required": [...],
        "types": {...},
        "patterns": {...}
    },
    "post_process": {
        # Post-processing options (optional)
        "remove_null": bool,
        "remove_empty": bool,
        "flatten": bool
    },
    "strict": bool  # Fail on any field error (default: False)
}
```

### Field Mapping Specifications

#### Simple Path

```python
{
    "email": "contact.email"
}
```

#### Object Specification

```python
{
    "email": {
        "source": "contact.email",      # Source path
        "transform": "lowercase",         # Transformation
        "default": "unknown@example.com"  # Default value
    }
}
```

#### Static Value

```python
{
    "type": {
        "value": "customer"  # Static value
    }
}
```

#### Template

```python
{
    "full_name": {
        "template": "{{first_name}} {{last_name}}"
    }
}
```

#### Formula

```python
{
    "total": {
        "formula": "price * quantity"
    }
}
```

#### Chained Transformations

```python
{
    "processed_name": {
        "source": "name",
        "transform": ["trim", "lowercase", "capitalize"]
    }
}
```

### Nested Output

Create nested structures in output:

```python
{
    "fields": {
        "user.email": "email",
        "user.profile.firstName": "first_name",
        "user.profile.lastName": "last_name"
    }
}
```

**Output:**
```json
{
  "user": {
    "email": "john@example.com",
    "profile": {
      "firstName": "John",
      "lastName": "Doe"
    }
  }
}
```

---

## Transformations

### String Transformations

| Transform | Description | Example |
|-----------|-------------|---------|
| `uppercase` | Convert to uppercase | `"hello"` → `"HELLO"` |
| `lowercase` | Convert to lowercase | `"HELLO"` → `"hello"` |
| `trim` | Remove whitespace | `" hello "` → `"hello"` |
| `capitalize` | Capitalize first letter | `"hello"` → `"Hello"` |
| `title` | Title case | `"hello world"` → `"Hello World"` |
| `slug` | URL-safe slug | `"Hello World!"` → `"hello-world"` |
| `truncate:N` | Truncate to N chars | `truncate:5` → `"hello..."` |
| `replace:old,new` | Replace substring | `replace:hello,hi` |
| `split:delimiter` | Split into array | `split:,` |
| `join:delimiter` | Join array | `join:, ` |

**Examples:**

```python
# Uppercase
{"transform": "uppercase"}
"hello" → "HELLO"

# Truncate
{"transform": "truncate:10"}
"This is a long text" → "This is a ..."

# Replace
{"transform": "replace:Mr.,Dr."}
"Mr. Smith" → "Dr. Smith"

# Slug
{"transform": "slug"}
"Hello World!" → "hello-world"
```

### Number Transformations

| Transform | Description | Example |
|-----------|-------------|---------|
| `round:N` | Round to N decimals | `3.14159` → `3.14` |
| `floor` | Floor division | `3.7` → `3` |
| `ceil` | Ceiling | `3.2` → `4` |
| `abs` | Absolute value | `-5` → `5` |
| `format_currency:CUR` | Format as currency | `1234.56` → `"$1,234.56"` |
| `format_number:N` | Format with decimals | `1234.5678` → `"1,234.57"` |

**Examples:**

```python
# Round
{"transform": "round:2"}
3.14159 → 3.14

# Format currency
{"transform": "format_currency:USD"}
1234.56 → "$1,234.56"

{"transform": "format_currency:EUR"}
1234.56 → "€1,234.56"

# Format number
{"transform": "format_number:2"}
1234.5678 → "1,234.57"
```

### Date Transformations

| Transform | Description | Example |
|-----------|-------------|---------|
| `format_date:FORMAT` | Format date | `format_date:%Y-%m-%d` |
| `parse_date:FORMAT` | Parse date string | `parse_date:%Y-%m-%d` |
| `add_days:N` | Add N days | `add_days:7` |
| `add_hours:N` | Add N hours | `add_hours:24` |
| `timestamp` | Unix timestamp | `1700000000` |

**Date Format Codes:**
- `%Y` - Year (4 digits)
- `%m` - Month (01-12)
- `%d` - Day (01-31)
- `%H` - Hour (00-23)
- `%M` - Minute (00-59)
- `%S` - Second (00-59)
- `%B` - Month name (January)
- `%b` - Month abbr (Jan)
- `%A` - Weekday name (Monday)
- `%a` - Weekday abbr (Mon)

**Examples:**

```python
# Format date
{"transform": "format_date:%B %d, %Y"}
"2025-11-16" → "November 16, 2025"

{"transform": "format_date:%m/%d/%Y"}
"2025-11-16" → "11/16/2025"

# Add days
{"transform": "add_days:7"}
"2025-11-16" → "2025-11-23"

# Timestamp
{"transform": "timestamp"}
"2025-11-16T10:00:00" → 1731751200
```

### Type Conversions

| Transform | Description | Example |
|-----------|-------------|---------|
| `to_string` | Convert to string | `123` → `"123"` |
| `to_int` | Convert to integer | `"123"` → `123` |
| `to_float` | Convert to float | `"123.45"` → `123.45` |
| `to_bool` | Convert to boolean | `"true"` → `True` |

**Examples:**

```python
# to_int
{"transform": "to_int"}
"$1,234.56" → 1234  # Removes currency symbols

# to_bool
{"transform": "to_bool"}
"yes" → True
"no" → False
"1" → True
"0" → False
```

### Array Operations

| Transform | Description | Example |
|-----------|-------------|---------|
| `array_first` | First element | `[1,2,3]` → `1` |
| `array_last` | Last element | `[1,2,3]` → `3` |
| `array_length` | Array length | `[1,2,3]` → `3` |
| `array_join:delim` | Join elements | `array_join:, ` |
| `array_filter:cond` | Filter elements | `array_filter:not_null` |
| `array_map:transform` | Map transformation | `array_map:uppercase` |

**Examples:**

```python
# array_first
{"transform": "array_first"}
["apple", "banana", "cherry"] → "apple"

# array_join
{"transform": "array_join:, "}
["apple", "banana", "cherry"] → "apple, banana, cherry"

# array_filter
{"transform": "array_filter:not_null"}
["apple", null, "cherry", null] → ["apple", "cherry"]

# array_map
{"transform": "array_map:uppercase"}
["apple", "banana"] → ["APPLE", "BANANA"]
```

### Utility Transformations

| Transform | Description | Example |
|-----------|-------------|---------|
| `default:value` | Default if null | `default:N/A` |
| `coalesce` | First non-null | Returns first non-null value |

---

## Validation

### Validation Configuration

```python
{
    "validation": {
        "required": ["field1", "field2"],
        "types": {
            "field1": "string",
            "field2": "number"
        },
        "patterns": {
            "email": "^[^@]+@[^@]+\\.[^@]+$"
        }
    }
}
```

### Required Fields

Ensure fields are present and not empty:

```python
{
    "validation": {
        "required": ["email", "name", "phone"]
    }
}
```

**Validation Fails If:**
- Field is missing
- Field value is `None`
- Field value is empty string `""`

### Type Validation

Check field types:

```python
{
    "validation": {
        "types": {
            "email": "string",
            "age": "number",
            "active": "boolean",
            "tags": "array"
        }
    }
}
```

**Supported Types:**
- `string` - String type
- `number` - Integer or float
- `boolean` - Boolean
- `array` - List or tuple

### Pattern Validation

Validate using regex patterns:

```python
{
    "validation": {
        "patterns": {
            "email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
            "phone": "^\\+?[1-9]\\d{1,14}$",
            "zip_code": "^\\d{5}(-\\d{4})?$"
        }
    }
}
```

### Common Patterns

```python
# Email
"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

# Phone (E.164)
"^\\+?[1-9]\\d{1,14}$"

# URL
"^https?://[^\\s/$.?#].[^\\s]*$"

# UUID
"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# Zip Code (US)
"^\\d{5}(-\\d{4})?$"

# Credit Card
"^\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}$"
```

---

## Integration with Workflows

### Simple Transform Step

```json
{
  "id": "transform_data",
  "type": "transform",
  "config": {
    "transformations": {
      "email": {
        "source": "trigger.email",
        "transform": "lowercase"
      },
      "name": {
        "source": "trigger.name",
        "transform": "title"
      }
    }
  }
}
```

### Advanced Transform Step

```json
{
  "id": "map_contact_data",
  "type": "transform",
  "config": {
    "source": "trigger",
    "mapping_config": {
      "fields": {
        "Email": {
          "source": "email",
          "transform": "lowercase"
        },
        "FirstName": {
          "source": "first_name",
          "transform": "capitalize"
        },
        "FullName": {
          "template": "{{first_name}} {{last_name}}"
        }
      },
      "validation": {
        "required": ["Email"],
        "patterns": {
          "Email": "^[^@]+@[^@]+\\.[^@]+$"
        }
      }
    }
  }
}
```

### Using Transform Results

```json
{
  "id": "create_contact",
  "type": "action",
  "config": {
    "connection_id": "{{connections.salesforce}}",
    "action": "create_contact",
    "parameters": {
      "email": "{{steps.map_contact_data.result.Email}}",
      "first_name": "{{steps.map_contact_data.result.FirstName}}",
      "full_name": "{{steps.map_contact_data.result.FullName}}"
    }
  }
}
```

---

## Advanced Usage

### Complex Nested Mapping

```python
{
    "fields": {
        # Map nested input to flat output
        "customer_email": "order.customer.contact.email",
        "customer_phone": "order.customer.contact.phone",

        # Map flat input to nested output
        "user.profile.email": "email",
        "user.profile.name": "name",

        # Array indexing
        "first_item_name": "items[0].name",
        "first_item_price": "items[0].price",

        # Complex transformations
        "shipping_address": {
            "template": "{{order.shipping.street}}, {{order.shipping.city}}, {{order.shipping.state}} {{order.shipping.zip}}"
        }
    }
}
```

### Dynamic Field Mapping

```python
# In a workflow step
{
    "id": "dynamic_transform",
    "type": "transform",
    "config": {
        "source": "trigger",
        "mapping_config": {
            "fields": {
                # Use variables in templates
                "message": {
                    "template": "Hello {{name}}, your order #{{order_id}} total is {{total}}"
                },
                # Use formulas with variables
                "total_with_tax": {
                    "formula": "total * 1.08"
                }
            }
        }
    }
}
```

### Conditional Mapping

While the DataMapper doesn't support direct conditionals, you can combine with condition steps:

```json
{
  "id": "check_status",
  "type": "condition",
  "config": {
    "condition": "{{trigger.status}} == completed"
  }
},
{
  "id": "transform_completed",
  "type": "transform",
  "config": {
    "mapping_config": {
      "fields": {
        "status": {"value": "SUCCESS"},
        "message": {"template": "Order completed successfully"}
      }
    }
  }
}
```

### Batch Processing

Map multiple items in a loop:

```json
{
  "id": "loop_contacts",
  "type": "loop",
  "config": {
    "items": "{{trigger.contacts}}",
    "sub_steps": [
      {
        "id": "transform_contact",
        "type": "transform",
        "config": {
          "source": "loop.item",
          "mapping_config": {
            "fields": {
              "Email": "email",
              "Name": {
                "template": "{{first_name}} {{last_name}}"
              }
            }
          }
        }
      }
    ]
  }
}
```

---

## Best Practices

### 1. Always Validate Critical Fields

```python
{
    "fields": {...},
    "validation": {
        "required": ["email", "customer_id"],
        "patterns": {
            "email": "^[^@]+@[^@]+\\.[^@]+$"
        }
    }
}
```

### 2. Provide Default Values

```python
{
    "status": {
        "source": "status",
        "default": "pending"
    },
    "tier": {
        "source": "customer.tier",
        "default": "standard"
    }
}
```

### 3. Use Appropriate Transformations

```python
# Good: Chain related transformations
{
    "name": {
        "source": "name",
        "transform": ["trim", "title"]
    }
}

# Bad: Don't over-transform
{
    "name": {
        "source": "name",
        "transform": ["trim", "lowercase", "uppercase", "title"]
    }
}
```

### 4. Handle Null Values

```python
# Use post-processing to clean data
{
    "fields": {...},
    "post_process": {
        "remove_null": true,
        "remove_empty": true
    }
}

# Or use default values
{
    "phone": {
        "source": "phone",
        "default": "N/A"
    }
}
```

### 5. Document Complex Mappings

```python
# Add comments in workflow definitions
{
    "id": "complex_transform",
    "description": "Maps HubSpot contact format to Salesforce Lead format",
    "type": "transform",
    "config": {
        "mapping_config": {
            "fields": {
                # HubSpot uses 'email', Salesforce uses 'Email'
                "Email": "email",
                # Combine first and last name for full name
                "Name": {
                    "template": "{{firstname}} {{lastname}}"
                }
            }
        }
    }
}
```

### 6. Performance Considerations

```python
# Good: Simple transformations are fast
{
    "email": {
        "source": "email",
        "transform": "lowercase"
    }
}

# Caution: Complex formulas in loops may be slow
{
    "id": "loop_items",
    "type": "loop",
    "config": {
        "items": "{{large_array}}",
        "sub_steps": [{
            "type": "transform",
            "config": {
                "mapping_config": {
                    "fields": {
                        "complex_calc": {
                            "formula": "field1 * field2 + field3 / field4"
                        }
                    }
                }
            }
        }]
    }
}
```

### 7. Error Handling

```python
# Use strict mode for critical mappings
{
    "fields": {...},
    "strict": true  # Fail immediately on any error
}

# Use lenient mode for best-effort mappings
{
    "fields": {...},
    "strict": false  # Continue on field errors (default)
}
```

### 8. Testing

Test your mapping configurations:

```python
from app.services.workflows.data_mapper import get_data_mapper

# Test data
test_data = {
    "email": "JOHN@EXAMPLE.COM",
    "first_name": "john",
    "last_name": "doe"
}

# Mapping config
config = {
    "fields": {
        "email": {
            "source": "email",
            "transform": "lowercase"
        },
        "name": {
            "template": "{{first_name}} {{last_name}}",
            "transform": "title"
        }
    },
    "validation": {
        "required": ["email"],
        "patterns": {
            "email": "^[^@]+@[^@]+\\.[^@]+$"
        }
    }
}

# Map and validate
mapper = get_data_mapper()
result = mapper.map_fields(test_data, config)

print(result)
# {"email": "john@example.com", "name": "John Doe"}
```

---

## Error Handling

### DataMappingError

Raised when mapping fails:

```python
try:
    result = mapper.map_fields(source, config)
except DataMappingError as e:
    logger.error(f"Mapping failed: {e}")
    # Handle error
```

### ValidationError

Raised when validation fails:

```python
try:
    result = mapper.map_fields(source, config, validate=True)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    # Error message contains all validation failures
    # "Validation failed: Required field missing: email; Field age must be number"
```

### Common Errors

1. **Missing Source Field**: Source path doesn't exist
   - Solution: Use default values or check source data

2. **Invalid Transformation**: Unknown transformation name
   - Solution: Check transformation name spelling

3. **Type Mismatch**: Wrong type for transformation
   - Solution: Convert type before transforming

4. **Pattern Validation Failed**: Value doesn't match regex
   - Solution: Check pattern or transform value first

---

## Performance Tips

1. **Reuse DataMapper Instance**: Use singleton `get_data_mapper()`
2. **Avoid Deep Nesting**: Flatten data when possible
3. **Limit Formula Complexity**: Use simple calculations
4. **Cache Mapping Configs**: Don't rebuild configs repeatedly
5. **Batch Operations**: Process multiple items together when possible

---

## See Also

- [Data Mapping Examples](./DATA_MAPPING_EXAMPLES.md) - Practical examples
- [Workflow System Guide](./WORKFLOW_SYSTEM_GUIDE.md) - Workflow documentation
- [Integration Connectors](./NEW_CONNECTORS_SUMMARY.md) - Available connectors

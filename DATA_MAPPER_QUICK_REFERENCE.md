# Data Mapper Quick Reference

Quick reference guide for the Voicecon Data Mapping Engine.

## Quick Start

```python
from app.services.workflows.data_mapper import get_data_mapper

mapper = get_data_mapper()

result = mapper.map_fields(
    source_data={"name": "John", "email": "JOHN@EXAMPLE.COM"},
    mapping_config={
        "fields": {
            "email": {"source": "email", "transform": "lowercase"}
        }
    }
)
```

---

## Mapping Config Structure

```json
{
  "fields": {
    "target_field": "source.path" | mapping_spec
  },
  "validation": {
    "required": ["field1"],
    "types": {"field1": "string"},
    "patterns": {"field1": "regex"}
  },
  "post_process": {
    "remove_null": true,
    "remove_empty": true,
    "flatten": true
  },
  "strict": false
}
```

---

## Field Mapping Patterns

### Simple Path
```json
{"email": "contact.email"}
```

### With Transformation
```json
{
  "email": {
    "source": "contact.email",
    "transform": "lowercase"
  }
}
```

### Template
```json
{
  "full_name": {
    "template": "{{first_name}} {{last_name}}"
  }
}
```

### Formula
```json
{
  "total": {
    "formula": "price * quantity"
  }
}
```

### Static Value
```json
{
  "status": {
    "value": "active"
  }
}
```

### With Default
```json
{
  "tier": {
    "source": "tier",
    "default": "standard"
  }
}
```

### Chained Transformations
```json
{
  "name": {
    "source": "name",
    "transform": ["trim", "lowercase", "capitalize"]
  }
}
```

---

## Transformations Cheat Sheet

### String
| Transform | Example | Result |
|-----------|---------|--------|
| `uppercase` | `"hello"` | `"HELLO"` |
| `lowercase` | `"HELLO"` | `"hello"` |
| `trim` | `" hello "` | `"hello"` |
| `capitalize` | `"hello"` | `"Hello"` |
| `title` | `"hello world"` | `"Hello World"` |
| `slug` | `"Hello World!"` | `"hello-world"` |
| `truncate:10` | `"Long text..."` | `"Long text..."` |
| `replace:old,new` | `"hello"` | `"helio"` |

### Number
| Transform | Example | Result |
|-----------|---------|--------|
| `round:2` | `3.14159` | `3.14` |
| `floor` | `3.7` | `3` |
| `ceil` | `3.2` | `4` |
| `abs` | `-5` | `5` |
| `format_currency:USD` | `1234.56` | `"$1,234.56"` |
| `format_number:2` | `1234.5678` | `"1,234.57"` |

### Date
| Transform | Example | Result |
|-----------|---------|--------|
| `format_date:%Y-%m-%d` | `datetime` | `"2025-11-16"` |
| `format_date:%B %d, %Y` | `datetime` | `"November 16, 2025"` |
| `add_days:7` | `date` | `date + 7 days` |
| `add_hours:24` | `datetime` | `datetime + 24 hours` |
| `timestamp` | `datetime` | `1700000000` |

### Type Conversion
| Transform | Example | Result |
|-----------|---------|--------|
| `to_string` | `123` | `"123"` |
| `to_int` | `"123"` | `123` |
| `to_float` | `"123.45"` | `123.45` |
| `to_bool` | `"yes"` | `True` |

### Array
| Transform | Example | Result |
|-----------|---------|--------|
| `array_first` | `[1,2,3]` | `1` |
| `array_last` | `[1,2,3]` | `3` |
| `array_length` | `[1,2,3]` | `3` |
| `array_join:, ` | `["a","b"]` | `"a, b"` |
| `array_filter:not_null` | `[1,null,2]` | `[1,2]` |
| `array_map:uppercase` | `["a","b"]` | `["A","B"]` |

---

## Common Patterns

### Email Normalization
```json
{
  "email": {
    "source": "email",
    "transform": ["trim", "lowercase"]
  }
}
```

### Name Formatting
```json
{
  "full_name": {
    "template": "{{first_name}} {{last_name}}",
    "transform": "title"
  }
}
```

### Address Formatting
```json
{
  "address": {
    "template": "{{street}}, {{city}}, {{state}} {{zip}}"
  }
}
```

### Price Calculation
```json
{
  "total": {
    "formula": "price * quantity"
  },
  "total_with_tax": {
    "formula": "price * quantity * 1.08"
  }
}
```

### Date Formatting
```json
{
  "formatted_date": {
    "source": "created_at",
    "transform": "format_date:%B %d, %Y"
  }
}
```

### Phone Normalization
```json
{
  "phone": {
    "source": "phone",
    "transform": ["trim", "replace:-,", "replace: ,"]
  }
}
```

---

## Nested Data Access

### Reading Nested Fields
```json
{
  "customer_email": "order.customer.contact.email",
  "shipping_city": "order.shipping.address.city"
}
```

### Array Indexing
```json
{
  "first_item": "items[0].name",
  "first_item_price": "items[0].price"
}
```

### Creating Nested Output
```json
{
  "user.email": "email",
  "user.profile.name": "name",
  "user.address.city": "city"
}
```

Output:
```json
{
  "user": {
    "email": "...",
    "profile": {"name": "..."},
    "address": {"city": "..."}
  }
}
```

---

## Validation

### Required Fields
```json
{
  "validation": {
    "required": ["email", "name"]
  }
}
```

### Type Checking
```json
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

### Pattern Matching
```json
{
  "validation": {
    "patterns": {
      "email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
      "phone": "^\\+?[1-9]\\d{1,14}$",
      "zip": "^\\d{5}(-\\d{4})?$"
    }
  }
}
```

---

## Workflow Integration

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
      }
    }
  }
}
```

### Advanced Transform Step
```json
{
  "id": "map_data",
  "type": "transform",
  "config": {
    "source": "trigger",
    "mapping_config": {
      "fields": {
        "Email": "email",
        "Name": {"template": "{{first_name}} {{last_name}}"}
      },
      "validation": {
        "required": ["Email"]
      }
    }
  }
}
```

### Using Results
```json
{
  "id": "next_step",
  "type": "action",
  "config": {
    "parameters": {
      "email": "{{steps.map_data.result.Email}}"
    }
  }
}
```

---

## Date Format Codes

| Code | Description | Example |
|------|-------------|---------|
| `%Y` | Year (4 digits) | 2025 |
| `%y` | Year (2 digits) | 25 |
| `%m` | Month (01-12) | 11 |
| `%d` | Day (01-31) | 16 |
| `%H` | Hour (00-23) | 14 |
| `%I` | Hour (01-12) | 02 |
| `%M` | Minute (00-59) | 30 |
| `%S` | Second (00-59) | 45 |
| `%p` | AM/PM | PM |
| `%B` | Month name | November |
| `%b` | Month abbr | Nov |
| `%A` | Weekday | Saturday |
| `%a` | Weekday abbr | Sat |

---

## Common Regex Patterns

```python
# Email
"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

# Phone (E.164)
"^\\+?[1-9]\\d{1,14}$"

# URL
"^https?://[^\\s/$.?#].[^\\s]*$"

# UUID
"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# US Zip Code
"^\\d{5}(-\\d{4})?$"

# Credit Card
"^\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}$"

# ISO Date
"^\\d{4}-\\d{2}-\\d{2}$"

# Time (24h)
"^([01]\\d|2[0-3]):[0-5]\\d$"
```

---

## Error Handling

```python
from app.services.workflows.data_mapper import (
    get_data_mapper,
    DataMappingError,
    ValidationError
)

mapper = get_data_mapper()

try:
    result = mapper.map_fields(source, config)
except ValidationError as e:
    # Validation failed
    logger.error(f"Validation failed: {e}")
except DataMappingError as e:
    # Mapping failed
    logger.error(f"Mapping failed: {e}")
```

---

## Tips & Tricks

### 1. Combine Template + Transform
```json
{
  "full_name": {
    "template": "{{first}} {{last}}",
    "transform": "title"
  }
}
```

### 2. Use Defaults for Optional Fields
```json
{
  "tier": {
    "source": "tier",
    "default": "standard"
  }
}
```

### 3. Clean Data with Post-Processing
```json
{
  "fields": {...},
  "post_process": {
    "remove_null": true,
    "remove_empty": true
  }
}
```

### 4. Chain Related Transformations
```json
{
  "email": {
    "source": "email",
    "transform": ["trim", "lowercase"]
  }
}
```

### 5. Use Strict Mode for Critical Data
```json
{
  "fields": {...},
  "strict": true
}
```

---

## Complete Example

```json
{
  "fields": {
    "Email": {
      "source": "contact.email",
      "transform": ["trim", "lowercase"]
    },
    "FirstName": {
      "source": "contact.first_name",
      "transform": "capitalize"
    },
    "LastName": {
      "source": "contact.last_name",
      "transform": "capitalize"
    },
    "FullName": {
      "template": "{{contact.first_name}} {{contact.last_name}}",
      "transform": "title"
    },
    "Phone": {
      "source": "contact.phone",
      "transform": "trim",
      "default": ""
    },
    "CreatedDate": {
      "source": "created_at",
      "transform": "format_date:%Y-%m-%d"
    },
    "CustomerType": {
      "value": "prospect"
    },
    "TotalValue": {
      "formula": "order_value * 1.08"
    }
  },
  "validation": {
    "required": ["Email", "FirstName", "LastName"],
    "types": {
      "Email": "string",
      "TotalValue": "number"
    },
    "patterns": {
      "Email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
    }
  },
  "post_process": {
    "remove_null": true
  }
}
```

---

## Resources

- **Full Guide**: [DATA_MAPPER_GUIDE.md](DATA_MAPPER_GUIDE.md)
- **Examples**: [DATA_MAPPING_EXAMPLES.md](DATA_MAPPING_EXAMPLES.md)
- **Summary**: [DATA_MAPPER_SUMMARY.md](DATA_MAPPER_SUMMARY.md)
- **Workflow Guide**: [WORKFLOW_SYSTEM_GUIDE.md](WORKFLOW_SYSTEM_GUIDE.md)

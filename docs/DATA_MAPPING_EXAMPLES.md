# Data Mapping Examples

This document provides comprehensive examples of using the DataMapper in workflows.

## Table of Contents

1. [Simple Field Mapping](#simple-field-mapping)
2. [Field Transformations](#field-transformations)
3. [Template Mapping](#template-mapping)
4. [Formula-Based Mapping](#formula-based-mapping)
5. [Array Operations](#array-operations)
6. [Nested Object Mapping](#nested-object-mapping)
7. [Advanced Transform Steps](#advanced-transform-steps)
8. [Real-World Examples](#real-world-examples)

---

## Simple Field Mapping

Map fields directly from source to target:

```json
{
  "fields": {
    "email": "contact.email",
    "firstName": "contact.first_name",
    "lastName": "contact.last_name",
    "phone": "contact.phone"
  }
}
```

**Input:**
```json
{
  "contact": {
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1234567890"
  }
}
```

**Output:**
```json
{
  "email": "john@example.com",
  "firstName": "John",
  "lastName": "Doe",
  "phone": "+1234567890"
}
```

---

## Field Transformations

### String Transformations

```json
{
  "fields": {
    "emailUpper": {
      "source": "email",
      "transform": "uppercase"
    },
    "nameLower": {
      "source": "name",
      "transform": "lowercase"
    },
    "slug": {
      "source": "title",
      "transform": "slug"
    },
    "shortBio": {
      "source": "bio",
      "transform": "truncate:100"
    }
  }
}
```

### Chained Transformations

```json
{
  "fields": {
    "processedName": {
      "source": "name",
      "transform": ["trim", "lowercase", "capitalize"]
    },
    "formattedPhone": {
      "source": "phone",
      "transform": ["trim", {"name": "replace", "args": "-,"}]
    }
  }
}
```

### Number Transformations

```json
{
  "fields": {
    "roundedPrice": {
      "source": "price",
      "transform": "round:2"
    },
    "formattedAmount": {
      "source": "amount",
      "transform": "format_currency:USD"
    },
    "percentage": {
      "source": "value",
      "transform": "format_number:2"
    }
  }
}
```

### Date Transformations

```json
{
  "fields": {
    "formattedDate": {
      "source": "created_at",
      "transform": "format_date:%B %d, %Y"
    },
    "futureDate": {
      "source": "start_date",
      "transform": "add_days:7"
    },
    "timestamp": {
      "source": "event_time",
      "transform": "timestamp"
    }
  }
}
```

---

## Template Mapping

Combine multiple fields using templates:

```json
{
  "fields": {
    "fullName": {
      "template": "{{first_name}} {{last_name}}"
    },
    "address": {
      "template": "{{street}}, {{city}}, {{state}} {{zip}}"
    },
    "greeting": {
      "template": "Hello {{title}} {{last_name}}, welcome to {{company}}!"
    }
  }
}
```

**Input:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "title": "Mr.",
  "company": "Acme Corp",
  "street": "123 Main St",
  "city": "New York",
  "state": "NY",
  "zip": "10001"
}
```

**Output:**
```json
{
  "fullName": "John Doe",
  "address": "123 Main St, New York, NY 10001",
  "greeting": "Hello Mr. Doe, welcome to Acme Corp!"
}
```

---

## Formula-Based Mapping

Perform calculations using formulas:

```json
{
  "fields": {
    "total": {
      "formula": "price * quantity"
    },
    "totalWithTax": {
      "formula": "price * quantity * 1.08"
    },
    "discount": {
      "formula": "price * discount_percentage / 100"
    },
    "finalPrice": {
      "formula": "price - (price * discount_percentage / 100)"
    }
  }
}
```

**Input:**
```json
{
  "price": 100,
  "quantity": 3,
  "discount_percentage": 10
}
```

**Output:**
```json
{
  "total": 300,
  "totalWithTax": 324,
  "discount": 10,
  "finalPrice": 90
}
```

---

## Array Operations

### Array Field Extraction

```json
{
  "fields": {
    "firstItem": {
      "source": "items",
      "transform": "array_first"
    },
    "lastItem": {
      "source": "items",
      "transform": "array_last"
    },
    "itemCount": {
      "source": "items",
      "transform": "array_length"
    },
    "itemsList": {
      "source": "items",
      "transform": "array_join:, "
    }
  }
}
```

### Array with Index

Access specific array elements:

```json
{
  "fields": {
    "firstProductName": "products[0].name",
    "firstProductPrice": "products[0].price",
    "secondProductName": "products[1].name"
  }
}
```

### Array Filtering and Mapping

```json
{
  "fields": {
    "validEmails": {
      "source": "emails",
      "transform": "array_filter:not_null"
    },
    "uppercaseNames": {
      "source": "names",
      "transform": "array_map:uppercase"
    }
  }
}
```

---

## Nested Object Mapping

### Deep Nesting

```json
{
  "fields": {
    "customerEmail": "order.customer.contact.email",
    "shippingCity": "order.shipping.address.city",
    "billingStreet": "order.billing.address.street",
    "productName": "order.items[0].product.name"
  }
}
```

### Creating Nested Output

```json
{
  "fields": {
    "user.email": "email",
    "user.profile.firstName": "first_name",
    "user.profile.lastName": "last_name",
    "user.address.city": "city",
    "user.address.country": "country"
  }
}
```

**Input:**
```json
{
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "city": "New York",
  "country": "USA"
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
    },
    "address": {
      "city": "New York",
      "country": "USA"
    }
  }
}
```

---

## Advanced Transform Steps

### Simple Transform Step (Workflow)

```json
{
  "id": "transform_contact",
  "type": "transform",
  "config": {
    "transformations": {
      "email": {
        "source": "trigger.email",
        "transform": "lowercase"
      },
      "fullName": {
        "source": "trigger.first_name",
        "transform": "title"
      },
      "createdAt": {
        "value": "2025-11-16",
        "transform": "format_date:%B %d, %Y"
      }
    }
  }
}
```

### Advanced Transform Step with DataMapper

```json
{
  "id": "map_salesforce_contact",
  "type": "transform",
  "config": {
    "source": "trigger",
    "mapping_config": {
      "fields": {
        "Email": "email",
        "FirstName": {
          "source": "first_name",
          "transform": "capitalize"
        },
        "LastName": {
          "source": "last_name",
          "transform": "capitalize"
        },
        "Phone": {
          "source": "phone",
          "transform": "trim"
        },
        "Company": {
          "template": "{{company_name}} Inc."
        }
      },
      "validation": {
        "required": ["Email", "FirstName", "LastName"],
        "types": {
          "Email": "string",
          "Phone": "string"
        },
        "patterns": {
          "Email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        }
      }
    }
  }
}
```

---

## Real-World Examples

### Example 1: HubSpot to Salesforce Contact Sync

**Scenario:** Sync a contact from HubSpot to Salesforce with field mapping and validation.

```json
{
  "id": "hubspot_to_salesforce",
  "type": "transform",
  "config": {
    "source": "steps.get_hubspot_contact.result",
    "mapping_config": {
      "fields": {
        "Email": "properties.email",
        "FirstName": {
          "source": "properties.firstname",
          "transform": "capitalize"
        },
        "LastName": {
          "source": "properties.lastname",
          "transform": "capitalize"
        },
        "Phone": {
          "source": "properties.phone",
          "transform": "trim"
        },
        "Title": "properties.jobtitle",
        "Company": "properties.company",
        "Description": {
          "template": "Contact imported from HubSpot on {{import_date}}"
        }
      },
      "validation": {
        "required": ["Email"],
        "types": {
          "Email": "string",
          "FirstName": "string",
          "LastName": "string"
        },
        "patterns": {
          "Email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        }
      }
    }
  }
}
```

### Example 2: Call Data to Google Calendar Event

**Scenario:** Create a Google Calendar event from call completion data.

```json
{
  "id": "call_to_calendar",
  "type": "transform",
  "config": {
    "source": "trigger",
    "mapping_config": {
      "fields": {
        "summary": {
          "template": "Call with {{customer_name}} - {{call_status}}"
        },
        "description": {
          "template": "Call Duration: {{duration}} seconds\\nTranscript: {{transcript}}"
        },
        "start_time": {
          "source": "start_time",
          "transform": "format_date:%Y-%m-%dT%H:%M:%S"
        },
        "end_time": {
          "source": "end_time",
          "transform": "format_date:%Y-%m-%dT%H:%M:%S"
        },
        "attendees": {
          "source": "customer_email"
        }
      }
    }
  }
}
```

### Example 3: E-commerce Order to Stripe Payment

**Scenario:** Transform order data to create a Stripe payment intent.

```json
{
  "id": "order_to_stripe",
  "type": "transform",
  "config": {
    "source": "steps.get_order.result",
    "mapping_config": {
      "fields": {
        "amount": {
          "formula": "total * 100"
        },
        "currency": {
          "value": "usd"
        },
        "description": {
          "template": "Order #{{order_id}} - {{item_count}} items"
        },
        "metadata.order_id": "order_id",
        "metadata.customer_email": "customer.email",
        "metadata.customer_name": {
          "template": "{{customer.first_name}} {{customer.last_name}}"
        }
      }
    }
  }
}
```

### Example 4: Call Analytics to Slack Notification

**Scenario:** Send a formatted Slack notification with call analytics.

```json
{
  "id": "analytics_to_slack",
  "type": "transform",
  "config": {
    "source": "steps.calculate_analytics.result",
    "mapping_config": {
      "fields": {
        "text": {
          "template": "Daily Call Report"
        },
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": {
                "template": "*Total Calls:* {{total_calls}}\\n*Successful:* {{successful_calls}}\\n*Failed:* {{failed_calls}}\\n*Avg Duration:* {{avg_duration}} sec"
              }
            }
          }
        ]
      },
      "post_process": {
        "remove_null": true
      }
    }
  }
}
```

### Example 5: Multi-Source Data Aggregation

**Scenario:** Combine data from multiple sources (call, CRM, calendar).

```json
{
  "id": "aggregate_customer_data",
  "type": "transform",
  "config": {
    "mapping_config": {
      "fields": {
        "customer_id": "trigger.customer_id",
        "email": "steps.get_crm_contact.result.email",
        "name": {
          "template": "{{steps.get_crm_contact.result.first_name}} {{steps.get_crm_contact.result.last_name}}"
        },
        "last_call_date": {
          "source": "trigger.call_completed_at",
          "transform": "format_date:%Y-%m-%d"
        },
        "next_meeting": {
          "source": "steps.get_next_event.result.start_time",
          "transform": "format_date:%B %d, %Y at %I:%M %p"
        },
        "total_calls": {
          "source": "steps.get_call_history.result",
          "transform": "array_length"
        },
        "customer_tier": {
          "source": "steps.get_crm_contact.result.tier",
          "default": "standard"
        }
      },
      "validation": {
        "required": ["customer_id", "email"],
        "types": {
          "customer_id": "string",
          "email": "string",
          "total_calls": "number"
        }
      }
    }
  }
}
```

---

## Post-Processing Options

### Remove Null Values

```json
{
  "fields": {
    "name": "name",
    "email": "email",
    "phone": "phone"
  },
  "post_process": {
    "remove_null": true
  }
}
```

### Remove Empty Strings

```json
{
  "fields": {
    "name": "name",
    "email": "email"
  },
  "post_process": {
    "remove_empty": true
  }
}
```

### Flatten Nested Objects

```json
{
  "fields": {
    "user.name": "name",
    "user.email": "email"
  },
  "post_process": {
    "flatten": true
  }
}
```

**Output:**
```json
{
  "user_name": "John",
  "user_email": "john@example.com"
}
```

---

## Validation Examples

### Required Fields

```json
{
  "fields": {
    "email": "email",
    "name": "name"
  },
  "validation": {
    "required": ["email", "name"]
  }
}
```

### Type Validation

```json
{
  "fields": {
    "email": "email",
    "age": "age",
    "active": "is_active",
    "tags": "tags"
  },
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

### Pattern Validation

```json
{
  "fields": {
    "email": "email",
    "phone": "phone",
    "zip": "zip_code"
  },
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

## Available Transformations

### String Transformations
- `uppercase` - Convert to uppercase
- `lowercase` - Convert to lowercase
- `trim` - Remove whitespace
- `capitalize` - Capitalize first letter
- `title` - Title case
- `slug` - URL-safe slug
- `truncate:N` - Truncate to N characters
- `replace:old,new` - Replace substring
- `split:delimiter` - Split into array
- `join:delimiter` - Join array into string

### Number Transformations
- `round:N` - Round to N decimals
- `floor` - Floor division
- `ceil` - Ceiling
- `abs` - Absolute value
- `format_currency:CURRENCY` - Format as currency (USD, EUR, GBP)
- `format_number:N` - Format with N decimals

### Date Transformations
- `format_date:FORMAT` - Format date (strftime format)
- `parse_date:FORMAT` - Parse date string
- `add_days:N` - Add N days
- `add_hours:N` - Add N hours
- `timestamp` - Convert to Unix timestamp

### Type Conversions
- `to_string` - Convert to string
- `to_int` - Convert to integer
- `to_float` - Convert to float
- `to_bool` - Convert to boolean

### Array Operations
- `array_first` - Get first element
- `array_last` - Get last element
- `array_length` - Get array length
- `array_join:delimiter` - Join array elements
- `array_filter:condition` - Filter array (not_null, truthy)
- `array_map:transform` - Map transformation over array

### Utilities
- `default:value` - Use default if null
- `coalesce` - Return first non-null value

---

## Complete Workflow Example

```json
{
  "name": "Call to CRM and Calendar Sync",
  "trigger_type": "call_completed",
  "workflow_steps": [
    {
      "id": "transform_call_data",
      "type": "transform",
      "config": {
        "source": "trigger",
        "mapping_config": {
          "fields": {
            "customer_email": "customer.email",
            "customer_name": {
              "template": "{{customer.first_name}} {{customer.last_name}}"
            },
            "call_duration": {
              "source": "duration",
              "transform": "to_int"
            },
            "call_date": {
              "source": "completed_at",
              "transform": "format_date:%Y-%m-%d"
            },
            "call_summary": {
              "template": "Call with {{customer.first_name}} lasted {{duration}} seconds"
            }
          }
        }
      }
    },
    {
      "id": "update_crm",
      "type": "action",
      "config": {
        "connection_id": "{{connections.salesforce}}",
        "action": "update_contact",
        "parameters": {
          "email": "{{steps.transform_call_data.result.customer_email}}",
          "last_call_date": "{{steps.transform_call_data.result.call_date}}",
          "description": "{{steps.transform_call_data.result.call_summary}}"
        }
      }
    },
    {
      "id": "create_calendar_event",
      "type": "action",
      "config": {
        "connection_id": "{{connections.google_calendar}}",
        "action": "create_event",
        "parameters": {
          "summary": "Follow-up: {{steps.transform_call_data.result.customer_name}}",
          "start_time": "{{trigger.completed_at}}",
          "end_time": "{{trigger.completed_at}}",
          "description": "{{steps.transform_call_data.result.call_summary}}"
        }
      }
    }
  ]
}
```

---

## Tips and Best Practices

1. **Use Validation**: Always validate critical fields to catch errors early
2. **Chain Transformations**: Apply multiple transformations in sequence for complex operations
3. **Default Values**: Provide defaults for optional fields to avoid null errors
4. **Template vs Formula**: Use templates for string concatenation, formulas for calculations
5. **Array Indexing**: Remember arrays are 0-indexed: `items[0]` is the first item
6. **Date Formats**: Use Python strftime format codes for date formatting
7. **Error Handling**: Set `strict: false` in mapping config to continue on field errors
8. **Performance**: Use simple transformations when possible, avoid complex formulas in loops

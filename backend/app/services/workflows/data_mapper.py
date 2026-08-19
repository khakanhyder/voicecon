"""
Data Mapping Engine.

Comprehensive data mapping and transformation system for workflows.
"""
import logging
import re
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime, date
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


class DataMappingError(Exception):
    """Raised when data mapping fails."""
    pass


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class DataMapper:
    """
    Data mapping and transformation engine.

    Supports:
    - Field mapping with dot notation
    - Type transformations
    - String operations
    - Date/time formatting
    - Number formatting
    - Array operations
    - Custom formulas
    - Nested object handling
    - Data validation
    """

    def __init__(self):
        """Initialize data mapper."""
        self.transformations = {
            # String transformations
            "uppercase": self._uppercase,
            "lowercase": self._lowercase,
            "trim": self._trim,
            "capitalize": self._capitalize,
            "title": self._title,
            "slug": self._slug,
            "truncate": self._truncate,
            "replace": self._replace,
            "split": self._split,
            "join": self._join,

            # Number transformations
            "round": self._round,
            "floor": self._floor,
            "ceil": self._ceil,
            "abs": self._abs,
            "format_currency": self._format_currency,
            "format_number": self._format_number,

            # Date transformations
            "format_date": self._format_date,
            "parse_date": self._parse_date,
            "add_days": self._add_days,
            "add_hours": self._add_hours,
            "timestamp": self._timestamp,

            # Type conversions
            "to_string": self._to_string,
            "to_int": self._to_int,
            "to_float": self._to_float,
            "to_bool": self._to_bool,

            # Array operations
            "array_first": self._array_first,
            "array_last": self._array_last,
            "array_length": self._array_length,
            "array_join": self._array_join,
            "array_filter": self._array_filter,
            "array_map": self._array_map,
            "pluck": self._pluck,

            # Aggregations. Each takes an optional field name so a list of
            # objects can be totalled directly ("sum:amount"), which is what
            # the Set Fields builder emits — without it every aggregate would
            # need a separate pluck step the UI has no way to express.
            "count": self._count,
            "sum": self._sum,
            "average": self._average,
            "min_value": self._min_value,
            "max_value": self._max_value,

            # Utilities
            "default": self._default,
            "coalesce": self._coalesce,
        }

    def map_fields(
        self,
        source_data: Dict[str, Any],
        mapping_config: Dict[str, Any],
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Map source data to target format using mapping configuration.

        Args:
            source_data: Source data dictionary
            mapping_config: Mapping configuration
            validate: Whether to validate output

        Returns:
            Mapped data dictionary

        Raises:
            DataMappingError: If mapping fails
            ValidationError: If validation fails
        """
        try:
            result = {}

            # Get field mappings
            field_mappings = mapping_config.get("fields", {})

            for target_field, mapping_spec in field_mappings.items():
                try:
                    value = self._map_field(source_data, mapping_spec)
                    self._set_nested_value(result, target_field, value)
                except Exception as e:
                    logger.warning(f"Failed to map field {target_field}: {e}")
                    # Continue with other fields unless strict mode
                    if mapping_config.get("strict", False):
                        raise

            # Apply post-processing if defined
            if "post_process" in mapping_config:
                result = self._apply_post_processing(result, mapping_config["post_process"])

            # Validate output if requested
            if validate and "validation" in mapping_config:
                self._validate_output(result, mapping_config["validation"])

            return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Data mapping failed: {e}", exc_info=True)
            raise DataMappingError(f"Data mapping failed: {str(e)}")

    def _map_field(
        self,
        source_data: Dict[str, Any],
        mapping_spec: Union[str, Dict[str, Any]],
    ) -> Any:
        """
        Map a single field.

        Args:
            source_data: Source data
            mapping_spec: Mapping specification (string path or dict config)

        Returns:
            Mapped value
        """
        # Simple string path
        if isinstance(mapping_spec, str):
            return self._get_nested_value(source_data, mapping_spec)

        # Complex mapping configuration
        if isinstance(mapping_spec, dict):
            # Get source value
            source_path = mapping_spec.get("source")
            if source_path:
                value = self._get_nested_value(source_data, source_path)
            elif "value" in mapping_spec:
                value = mapping_spec["value"]  # Static value
            else:
                value = None

            # Apply transformations
            if "transform" in mapping_spec:
                transform_spec = mapping_spec["transform"]
                if isinstance(transform_spec, str):
                    value = self.apply_transformation(value, transform_spec)
                elif isinstance(transform_spec, list):
                    # Chain of transformations
                    for transform in transform_spec:
                        value = self.apply_transformation(value, transform)

            # Apply template
            if "template" in mapping_spec:
                value = self._apply_template(source_data, mapping_spec["template"])

            # Apply formula
            if "formula" in mapping_spec:
                value = self._apply_formula(source_data, mapping_spec["formula"])

            # Apply default
            if value is None and "default" in mapping_spec:
                value = mapping_spec["default"]

            return value

        return mapping_spec  # Literal value

    def apply_transformation(
        self,
        value: Any,
        transform_spec: Union[str, Dict[str, Any]],
    ) -> Any:
        """
        Apply transformation to a value.

        Args:
            value: Value to transform
            transform_spec: Transformation specification

        Returns:
            Transformed value

        Raises:
            DataMappingError: If transformation fails
        """
        try:
            # Parse transformation spec
            if isinstance(transform_spec, str):
                # Simple transformation: "uppercase" or "truncate:10"
                if ":" in transform_spec:
                    parts = transform_spec.split(":", 1)
                    transform_name = parts[0].strip()
                    transform_args = parts[1].strip()
                else:
                    transform_name = transform_spec
                    transform_args = None
            elif isinstance(transform_spec, dict):
                transform_name = transform_spec.get("name")
                transform_args = transform_spec.get("args")
            else:
                raise DataMappingError(f"Invalid transformation spec: {transform_spec}")

            # Get transformation function
            if transform_name not in self.transformations:
                raise DataMappingError(f"Unknown transformation: {transform_name}")

            transform_func = self.transformations[transform_name]

            # Apply transformation
            if transform_args is not None:
                return transform_func(value, transform_args)
            else:
                return transform_func(value)

        except Exception as e:
            logger.error(f"Transformation {transform_spec} failed: {e}")
            raise DataMappingError(f"Transformation failed: {str(e)}")

    # ========================================================================
    # String Transformations
    # ========================================================================

    def _text(self, value: Any) -> str:
        """
        Coerce a value to text for a string transform.

        Rejects lists and objects rather than falling back to ``str()``: that
        would produce a Python repr — ``[]``, ``{'sku': 'A-1'}`` — which a Speak
        step reads to the caller verbatim. A container reaching a text transform
        is a configuration mistake, and saying so beats voicing punctuation.
        """
        if value is None:
            return ""
        if isinstance(value, (list, tuple, dict, set)):
            raise DataMappingError(
                f"expected text but got a {type(value).__name__}. "
                f"Pick a single value, or use a list transform first."
            )
        return str(value)

    def _uppercase(self, value: Any) -> str:
        """Convert to uppercase."""
        return self._text(value).upper()

    def _lowercase(self, value: Any) -> str:
        """Convert to lowercase."""
        return self._text(value).lower()

    def _trim(self, value: Any) -> str:
        """Trim whitespace."""
        return self._text(value).strip()

    def _capitalize(self, value: Any) -> str:
        """Capitalize first letter."""
        return self._text(value).capitalize()

    def _title(self, value: Any) -> str:
        """Title case."""
        return self._text(value).title()

    def _slug(self, value: Any) -> str:
        """Convert to URL-safe slug."""
        slug = self._text(value).lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')

    def _truncate(self, value: Any, length: Union[str, int] = 100) -> str:
        """Truncate to specified length."""
        length = int(length)
        text = self._text(value)
        if len(text) <= length:
            return text
        return text[:length] + "..."

    def _replace(self, value: Any, args: str) -> str:
        """Replace substring. Args format: 'old,new'"""
        if value is None:
            return ""
        parts = args.split(",", 1)
        if len(parts) != 2:
            raise DataMappingError("Replace requires 'old,new' format")
        old, new = parts
        return str(value).replace(old, new)

    def _split(self, value: Any, delimiter: str = ",") -> List[str]:
        """Split string into array."""
        if value is None:
            return []
        return str(value).split(delimiter)

    def _join(self, value: Any, delimiter: str = ",") -> str:
        """Join array into string."""
        if not isinstance(value, (list, tuple)):
            return str(value) if value is not None else ""
        return delimiter.join(str(item) for item in value)

    # ========================================================================
    # Number Transformations
    # ========================================================================

    def _round(self, value: Any, decimals: Union[str, int] = 0) -> float:
        """Round to specified decimals."""
        decimals = int(decimals)
        return round(float(value), decimals)

    def _floor(self, value: Any) -> int:
        """Floor division."""
        import math
        return math.floor(float(value))

    def _ceil(self, value: Any) -> int:
        """Ceiling."""
        import math
        return math.ceil(float(value))

    def _abs(self, value: Any) -> float:
        """Absolute value."""
        return abs(float(value))

    def _format_currency(self, value: Any, currency: str = "USD") -> str:
        """Format as currency."""
        amount = float(value)
        if currency == "USD":
            return f"${amount:,.2f}"
        elif currency == "EUR":
            return f"€{amount:,.2f}"
        elif currency == "GBP":
            return f"£{amount:,.2f}"
        else:
            return f"{currency} {amount:,.2f}"

    def _format_number(self, value: Any, decimals: Union[str, int] = 2) -> str:
        """Format number with commas."""
        decimals = int(decimals)
        return f"{float(value):,.{decimals}f}"

    # ========================================================================
    # Date Transformations
    # ========================================================================

    def _format_date(self, value: Any, format: str = "%Y-%m-%d") -> str:
        """Format date/datetime."""
        if isinstance(value, (datetime, date)):
            dt = value
        elif isinstance(value, str):
            # Try to parse ISO format
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                dt = datetime.strptime(value, "%Y-%m-%d")
        else:
            raise DataMappingError(f"Cannot format date: {value}")

        return dt.strftime(format)

    def _parse_date(self, value: Any, format: str = "%Y-%m-%d") -> datetime:
        """
        Parse a date string, ISO 8601 first.

        ISO is tried before the supplied format because that is what triggers
        and APIs actually send ("2026-08-20T09:30:00"), and the old
        strptime-only version rejected every one of them — which made
        Add days / Add hours / timestamp unusable on real data with the
        opaque error "unconverted data remains: T09:30:00".

        An explicit non-ISO format still works: ISO parsing only succeeds on
        ISO-shaped input, so anything else falls through to strptime.
        """
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)

        text = str(value).strip()

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass

        return datetime.strptime(text, format)

    def _add_days(self, value: Any, days: Union[str, int]) -> datetime:
        """Add days to date."""
        from datetime import timedelta
        days = int(days)
        if isinstance(value, str):
            value = self._parse_date(value)
        return value + timedelta(days=days)

    def _add_hours(self, value: Any, hours: Union[str, int]) -> datetime:
        """Add hours to datetime."""
        from datetime import timedelta
        hours = int(hours)
        if isinstance(value, str):
            value = self._parse_date(value)
        return value + timedelta(hours=hours)

    def _timestamp(self, value: Any) -> int:
        """Convert to Unix timestamp."""
        if isinstance(value, str):
            value = self._parse_date(value)
        return int(value.timestamp())

    # ========================================================================
    # Type Conversions
    # ========================================================================

    def _to_string(self, value: Any) -> str:
        """Convert to string."""
        if value is None:
            return ""
        return str(value)

    def _to_int(self, value: Any) -> int:
        """Convert to integer."""
        if value is None:
            return 0
        if isinstance(value, str):
            # Remove commas and currency symbols
            value = re.sub(r'[,$£€]', '', value)
        return int(float(value))

    def _to_float(self, value: Any) -> float:
        """Convert to float."""
        if value is None:
            return 0.0
        if isinstance(value, str):
            value = re.sub(r'[,$£€]', '', value)
        return float(value)

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        return bool(value)

    # ========================================================================
    # Array Operations
    # ========================================================================

    def _array_first(self, value: Any) -> Any:
        """Get first element of array."""
        if not isinstance(value, (list, tuple)):
            return value
        return value[0] if value else None

    def _array_last(self, value: Any) -> Any:
        """Get last element of array."""
        if not isinstance(value, (list, tuple)):
            return value
        return value[-1] if value else None

    def _array_length(self, value: Any) -> int:
        """Get array length."""
        if not isinstance(value, (list, tuple)):
            return 0
        return len(value)

    def _array_join(self, value: Any, delimiter: str = ",") -> str:
        """Join array elements."""
        return self._join(value, delimiter)

    def _array_filter(self, value: Any, condition: str) -> List[Any]:
        """Filter array elements."""
        if not isinstance(value, (list, tuple)):
            return []
        # Simple filter: "not_null", "truthy"
        if condition == "not_null":
            return [item for item in value if item is not None]
        elif condition == "truthy":
            return [item for item in value if item]
        return value

    def _array_map(self, value: Any, transform: str) -> List[Any]:
        """Map transformation over array."""
        if not isinstance(value, (list, tuple)):
            return []
        return [self.apply_transformation(item, transform) for item in value]

    def _pluck(self, value: Any, field: str) -> List[Any]:
        """Extract one field from every object in an array."""
        if not isinstance(value, (list, tuple)):
            return []
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(item.get(field))
            else:
                out.append(getattr(item, field, None))
        return out

    def _series(self, value: Any, field: Optional[str] = None) -> List[float]:
        """
        Coerce a value into a list of numbers for aggregation.

        Accepts a bare list of numbers, a list of objects plus a `field` to read
        from each, or a single scalar. Anything non-numeric is skipped rather
        than raising: one malformed row in an API response should not fail the
        whole workflow, and the alternative is a step error the builder user
        cannot act on.
        """
        if value is None:
            return []

        items = value if isinstance(value, (list, tuple)) else [value]

        if field:
            items = self._pluck(items, field)

        numbers: List[float] = []
        for item in items:
            if isinstance(item, bool) or item is None:
                continue
            if isinstance(item, (int, float, Decimal)):
                numbers.append(float(item))
                continue
            try:
                numbers.append(float(str(item).strip()))
            except (TypeError, ValueError):
                continue

        return numbers

    def _count(self, value: Any, field: Optional[str] = None) -> int:
        """Number of items in a list (0 for anything else)."""
        if isinstance(value, (list, tuple)):
            return len(value)
        if value is None or (isinstance(value, str) and not value.strip()):
            return 0
        return 1

    def _sum(self, value: Any, field: Optional[str] = None) -> float:
        """Total of a list of numbers, or of `field` across a list of objects."""
        return self._clean(sum(self._series(value, field)))

    def _average(self, value: Any, field: Optional[str] = None) -> Optional[float]:
        """Mean of a numeric series. None for an empty series, not 0."""
        numbers = self._series(value, field)
        if not numbers:
            return None
        return self._clean(sum(numbers) / len(numbers))

    def _min_value(self, value: Any, field: Optional[str] = None) -> Optional[float]:
        """Smallest number in a series, or None when there is nothing to compare."""
        numbers = self._series(value, field)
        return self._clean(min(numbers)) if numbers else None

    def _max_value(self, value: Any, field: Optional[str] = None) -> Optional[float]:
        """Largest number in a series, or None when there is nothing to compare."""
        numbers = self._series(value, field)
        return self._clean(max(numbers)) if numbers else None

    def _clean(self, number: float) -> float:
        """
        Render a float without binary-floating-point noise.

        ``0.1 + 0.2`` is ``0.30000000000000004``, and a workflow that speaks its
        result would read every one of those digits to the caller. Rounding to
        10 decimal places removes the artefact while leaving any precision a
        real monetary or measurement value could carry.
        """
        rounded = round(number, 10)
        return int(rounded) if rounded == int(rounded) else rounded

    # ========================================================================
    # Utilities
    # ========================================================================

    def _default(self, value: Any, default_value: Any) -> Any:
        """Return default if value is None."""
        return value if value is not None else default_value

    def _coalesce(self, *values: Any) -> Any:
        """Return first non-None value."""
        for value in values:
            if value is not None:
                return value
        return None

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get nested value using dot notation.

        Args:
            data: Source data dictionary
            path: Dot notation path (e.g., "user.address.city")

        Returns:
            Value at path or None
        """
        if not path:
            return data

        keys = path.split(".")
        value = data

        for key in keys:
            # Handle array indexing
            if "[" in key and "]" in key:
                # Parse array access: "items[0]"
                match = re.match(r'(\w+)\[(\d+)\]', key)
                if match:
                    array_key = match.group(1)
                    index = int(match.group(2))
                    value = value.get(array_key, [])
                    if isinstance(value, (list, tuple)) and 0 <= index < len(value):
                        value = value[index]
                    else:
                        return None
                else:
                    return None
            else:
                # Regular key access
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None

            if value is None:
                return None

        return value

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """
        Set nested value using dot notation.

        Args:
            data: Target data dictionary
            path: Dot notation path
            value: Value to set
        """
        if not path:
            return

        keys = path.split(".")
        current = data

        for i, key in enumerate(keys[:-1]):
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _apply_template(self, source_data: Dict[str, Any], template: str) -> str:
        """
        Apply template with variables.

        Args:
            source_data: Source data
            template: Template string with {{variables}}

        Returns:
            Rendered template
        """
        result = template

        # Find all {{variable}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, template)

        for match in matches:
            var_path = match.strip()
            var_value = self._get_nested_value(source_data, var_path)
            if var_value is not None:
                result = result.replace(f"{{{{{match}}}}}", str(var_value))

        return result

    def _apply_formula(self, source_data: Dict[str, Any], formula: str) -> Any:
        """
        Apply formula/expression.

        Args:
            source_data: Source data
            formula: Formula string

        Returns:
            Formula result
        """
        # Simple formula support
        # Format: "field1 + field2", "field * 100", etc.

        # Replace field references with values
        formula_eval = formula

        # Find field references (alphanumeric with dots)
        field_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_.]*)\b'
        fields = re.findall(field_pattern, formula)

        for field in fields:
            # Skip Python keywords/functions
            if field in ('and', 'or', 'not', 'in', 'is', 'if', 'else', 'True', 'False', 'None'):
                continue

            value = self._get_nested_value(source_data, field)
            if value is not None:
                # Replace field with value
                formula_eval = re.sub(
                    r'\b' + re.escape(field) + r'\b',
                    str(value),
                    formula_eval
                )

        # Evaluate safely (limited scope)
        try:
            # Only allow basic math operations
            allowed_names = {"__builtins__": {}}
            result = eval(formula_eval, allowed_names)
            return result
        except Exception as e:
            logger.warning(f"Formula evaluation failed: {formula} -> {e}")
            return None

    def _apply_post_processing(
        self,
        data: Dict[str, Any],
        post_process_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply post-processing to mapped data.

        Args:
            data: Mapped data
            post_process_config: Post-processing configuration

        Returns:
            Post-processed data
        """
        # Remove null values
        if post_process_config.get("remove_null", False):
            data = self._remove_null_values(data)

        # Remove empty strings
        if post_process_config.get("remove_empty", False):
            data = self._remove_empty_values(data)

        # Flatten nested objects
        if post_process_config.get("flatten", False):
            data = self._flatten_dict(data)

        return data

    def _remove_null_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove None values from dictionary."""
        return {k: v for k, v in data.items() if v is not None}

    def _remove_empty_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty strings from dictionary."""
        return {k: v for k, v in data.items() if v != ""}

    def _flatten_dict(
        self,
        data: Dict[str, Any],
        parent_key: str = "",
        sep: str = "_",
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _validate_output(
        self,
        data: Dict[str, Any],
        validation_config: Dict[str, Any],
    ) -> None:
        """
        Validate output data.

        Args:
            data: Data to validate
            validation_config: Validation rules

        Raises:
            ValidationError: If validation fails
        """
        errors = []

        # Required fields
        required = validation_config.get("required", [])
        for field in required:
            value = self._get_nested_value(data, field)
            if value is None or value == "":
                errors.append(f"Required field missing: {field}")

        # Type checks
        types = validation_config.get("types", {})
        for field, expected_type in types.items():
            value = self._get_nested_value(data, field)
            if value is not None:
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Field {field} must be string, got {type(value).__name__}")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Field {field} must be number, got {type(value).__name__}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Field {field} must be boolean, got {type(value).__name__}")
                elif expected_type == "array" and not isinstance(value, (list, tuple)):
                    errors.append(f"Field {field} must be array, got {type(value).__name__}")

        # Pattern checks
        patterns = validation_config.get("patterns", {})
        for field, pattern in patterns.items():
            value = self._get_nested_value(data, field)
            if value is not None:
                if not re.match(pattern, str(value)):
                    errors.append(f"Field {field} does not match pattern {pattern}")

        if errors:
            raise ValidationError(f"Validation failed: {'; '.join(errors)}")


# Singleton instance
_data_mapper: Optional[DataMapper] = None


def get_data_mapper() -> DataMapper:
    """
    Get data mapper instance (singleton).

    Returns:
        DataMapper instance
    """
    global _data_mapper
    if _data_mapper is None:
        _data_mapper = DataMapper()
    return _data_mapper

# Test Suite for Presenter

This directory contains a comprehensive test suite for the org-mode → Typst presentation generator.

## Structure

```
tests/
├── README.md           # This file
├── __init__.py         # Python module init
├── fixtures/           # Test data files
│   ├── basic.org       # Basic org file test case
│   ├── pdf_test.org    # PDF embedding test case
│   └── edge_cases.org  # Edge cases and error conditions
├── unit/               # Unit tests
│   ├── __init__.py
│   ├── test_pagemaker_api.py    # Core function tests (using pagemaker API)
│   └── test_edge_cases.py   # Edge case and error handling
└── integration/        # Integration tests
    ├── __init__.py
    └── test_pipeline.py     # Full pipeline tests

```

## Running Tests

### All Tests
```bash
make test
# or
python -m unittest discover tests -v
```

### Unit Tests Only
```bash
make test-unit
# or  
python -m unittest discover tests/unit -v
```

### Integration Tests Only
```bash
make test-integration
# or
python -m unittest discover tests/integration -v
```

### Individual Test Files
```bash
python -m unittest tests.unit.test_pagemaker_api -v
python -m unittest tests.integration.test_pipeline -v
```

## Test Coverage

Current test coverage includes:

### Core Functions (Unit Tests)
- ✅ `parse_area()` - Area string parsing with valid/invalid inputs
- ✅ `slugify()` - String slugification 
- ✅ `escape_text()` - Typst text escaping
- ✅ `meta_defaults()` - Metadata merging with defaults
- ✅ `OrgElement` class - Element creation and IR conversion

### Pipeline (Integration Tests)  
- ✅ Full org → IR → Typst conversion
- ✅ Basic org file processing
- ✅ PDF embedding functionality
- ✅ Image fit options
- ✅ Typst code generation

### Edge Cases & Error Handling
- ✅ Invalid area formats
- ✅ Missing required properties  
- ✅ Nonexistent files
- ✅ Malformed org syntax
- ✅ Empty/null inputs

## Test Fixtures

### basic.org
Standard org file with:
- Metadata (title, author, pagesize, etc.)
- Single slide with header, body, and figure elements
- Image with fit options

### pdf_test.org  
Tests PDF embedding:
- PDF element with muchpdf integration
- Page selection and scaling options

### edge_cases.org
Various edge cases:
- Missing AREA properties
- Invalid area formats
- Empty content sections
- Figures without image links

## Adding New Tests

### Unit Tests
Add to `tests/unit/test_pagemaker_api.py` or create new test files following the pattern:

```python
class TestNewFunction(unittest.TestCase):
    def test_basic_case(self):
        import pagemaker as pm
        result = pm.new_function("input")
        self.assertEqual(result, expected_output)
```

### Integration Tests
Add to `tests/integration/test_pipeline.py` for full pipeline tests:

```python
def test_new_feature(self):
    org_path = self.fixtures_path / "new_feature.org"
    import pagemaker as pm
    ir = pm.parse_org(str(org_path))
    typst_code = pm.generate_typst(ir)
    # Assert expected behavior
```

### Test Fixtures
Create new `.org` files in `tests/fixtures/` for specific test scenarios.

## Current Status

✅ **10 tests passing** - All core functionality covered  
⚠️ **1 deprecation warning** - datetime.utcnow() (low priority fix needed)

The test suite provides solid coverage of the presentation generation pipeline and helps ensure reliability when making changes.

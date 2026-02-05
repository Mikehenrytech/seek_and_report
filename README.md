# Seek and report


> *Searching and reporting Java patterns since 1983 🤘*

A lightweight Python tool to search for patterns in Java source code
with grep-like context, smart filtering, and a global threshold to
minimize noisy reports.

## Features

-   Search using **regex** or **literal** patterns\
-   Context around matches similar to `grep -A/-B`\
-   **Global threshold**: after X matches, switch to summary mode\
-   Automatic filtering of commented code:
    -   `// comments`
    -   `/* ... */`
    -   inline comments after `//`
-   Automatic exclusion of test sources under `/src/test/`
-   Optional **bold highlighting** for matched lines\
-   Optional **marker prefix** for environments without ANSI (default
    `==>`)\
-   Optional line numbers\
-   Relative paths for clean output\
-   Optional Windows style path separator (`\`)\
-   Optional export of the full report to a **.txt file** using a
    sanitized pattern as filename

------------------------------------------------------------------------

## Installation

Requires **Python 3.9+**.\
No external dependencies.

``` bash
chmod +x scan_context.py
```

Run directly:

``` bash
python3 scan_context.py <pattern> <root>
```

------------------------------------------------------------------------

## Basic Usage

### Search for printStackTrace ignoring comments and tests

``` bash
python3 scan_context.py "printStackTrace\(\);" .
```

### Case-insensitive search with bold highlighting

``` bash
python3 scan_context.py "printStackTrace\(\);" . -i --bold
```

### Literal (non-regex) search

``` bash
python3 scan_context.py ".printStackTrace();" . --literal
```

------------------------------------------------------------------------

## Marker Option (for non-ANSI environments)

When bold is not available (CI logs, plain text), use a marker prefix:

``` bash
python3 scan_context.py "pattern" . --marker "==>"
```

Custom marker:

``` bash
python3 scan_context.py "pattern" . --marker "[ALERT]"
```

Disable marker:

``` bash
python3 scan_context.py "pattern" . --marker ""
```

------------------------------------------------------------------------

## Context Control

### Show 3 lines before and 5 after

``` bash
python3 scan_context.py "pattern" . -B 3 -A 5
```

### Disable line numbers

``` bash
python3 scan_context.py "pattern" . --no-line-numbers
```

------------------------------------------------------------------------

## Global Threshold Mode

The tool uses a **GLOBAL match counter**:

-   The first **X matches** → printed with full context\
-   From match **X+1 onward** → only `path (line)` is shown

### Context only for first 10 matches

``` bash
python3 scan_context.py "pattern" . --max-context-total 10
```

### Include source line in summary mode

``` bash
python3 scan_context.py "pattern" . --max-context-total 10 --summary-line
```

### Always show context (disable threshold)

``` bash
python3 scan_context.py "pattern" . --max-context-total -1
```

------------------------------------------------------------------------

## Export Report to TXT

Generate a file named after the sanitized pattern:

``` bash
python3 scan_context.py "printStackTrace\(\);" . --export-txt
```

Export to a specific directory:

``` bash
python3 scan_context.py "printStackTrace\(\);" . --export-txt --export-dir reports
```

The filename is automatically sanitized to be safe for any filesystem.

------------------------------------------------------------------------

## Path Formatting

### Use Windows style separators

``` bash
python3 scan_context.py "pattern" . --separator-windows-os
```

Default separator is `/` for portability.

------------------------------------------------------------------------

## Filtering Rules

The scanner automatically ignores:

-   Files under `/src/test/`
-   Commented occurrences:
    -   Lines starting with `//`
    -   Lines starting with `/*` or `*`
    -   Matches appearing only after `//` in the same line

### Examples that are ignored

``` java
// e.printStackTrace();

/* e.printStackTrace(); */

logger.error("x"); // e.printStackTrace();
```

### Example that is detected

``` java
logger.error(e.getMessage());
e.printStackTrace();
```

------------------------------------------------------------------------

## Output Example

    src/main/java/com/app/Foo.java (95)

    90-    logger.info("start");
    91-    try {
    95:    ==> e.printStackTrace();
    96-    }

After threshold exceeded:

    src/main/java/com/app/Bar.java (120)
    src/main/java/com/app/Baz.java (44)

------------------------------------------------------------------------

## Final Report

    ==================================================
    Total coincidences: 37
    With context:       10
    In summary mode:    27
    ==================================================

------------------------------------------------------------------------

## All Options

    usage: scan_context.py [options] pattern [root]

    Options:
      -i, --ignore-case
      --literal
      --bold
      --marker
      -B N, --before N
      -A N, --after N
      -n, --line-numbers
      --no-line-numbers
      --max-context-total X
      --summary-line
      --separator-windows-os
      --export-txt
      --export-dir
      --include GLOB
      --exclude-dirs D1,D2
      --encoding ENC

------------------------------------------------------------------------

## Use Cases

-   Detect insecure logging such as `printStackTrace`
-   Locate `System.out` in production code\
-   Lightweight SAST pre-check\
-   Audit legacy Java projects\
-   Generate focused reports for SSDLC reviews

------------------------------------------------------------------------

## Recommended Security Patterns

``` bash
python3 scan_context.py "printStackTrace|System\.out|System\.err" . -i
```

``` bash
python3 scan_context.py "getMessage\(\)" . -i
```

------------------------------------------------------------------------

## License

Use freely for security auditing and code quality purposes.

------------------------------------------------------------------------

**Seek and report... they're looking for you!**

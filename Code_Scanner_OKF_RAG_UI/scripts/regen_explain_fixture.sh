#!/usr/bin/env bash
# Regenerate tests/fixtures/explain-okf with the real Java2OKF (needs Java 17+ and the built jar).
# The committed fixture was written to the Java2OKF OKF v0.2 spec (docs/okf-output.md) on a machine
# without a JVM; run this where Java is available and diff the result against the committed copy.
set -euo pipefail
JAR="${JAVA2OKF_JAR:-../../CodeScanner_1_java/java2okf/target/java2okf-1.0.0.jar}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
java -jar "$JAR" analyze --source "$HERE/tests/fixtures/explain-java" \
     --output "$HERE/tests/fixtures/explain-okf.generated" --project-name explain-fixture --no-timestamps --clean
echo "Generated: tests/fixtures/explain-okf.generated  (compare with tests/fixtures/explain-okf)"

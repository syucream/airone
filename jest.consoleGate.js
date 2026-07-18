let errorSpy;
let warnSpy;

const formatValue = (value) => {
  if (value instanceof Error) return value.stack ?? value.message;
  if (typeof value === "string") return value;

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const formatCalls = (label, calls) =>
  calls
    .map((args) => `${label}: ${args.map(formatValue).join(" ")}`)
    .join("\n\n");

beforeEach(() => {
  errorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);
  warnSpy = jest.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  const errors = errorSpy.mock.calls;
  const warnings = warnSpy.mock.calls;

  errorSpy.mockRestore();
  warnSpy.mockRestore();

  if (errors.length > 0 || warnings.length > 0) {
    const output = [
      formatCalls("console.error", errors),
      formatCalls("console.warn", warnings),
    ]
      .filter(Boolean)
      .join("\n\n");

    throw new Error(`Unexpected console output:\n\n${output}`);
  }
});

// Exit code taxonomy per design doc D10.
export const EXIT = {
  SUCCESS: 0,
  USAGE: 1,
  SCHEMA: 2,
  PARSE: 3,
  IO: 4,
  SETUP: 5,
} as const;

export type ExitCode = (typeof EXIT)[keyof typeof EXIT];

export function die(code: ExitCode, message: string): never {
  process.stderr.write(message.endsWith("\n") ? message : message + "\n");
  process.exit(code);
}

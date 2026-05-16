import { z } from "zod";

// Base fields shared across most artifact types. v1.12.0 (ecfd3c2) established
// the YAML frontmatter contract; this module mirrors it.
//
// All schemas use .passthrough() for tolerant evolution (D2): unknown fields
// pass through silently, known fields with wrong types fail explicitly.

const Base = z
  .object({
    type: z.enum(["design-doc", "handoff", "plan"]),
    version: z.number().int().min(1).optional(),
    status: z.enum(["DRAFT", "APPROVED", "SHIPPED"]).optional(),
    created: z.string().optional(),
    slug: z.string().optional(),
    branch: z.string().optional(),
    supersedes: z.string().nullable().optional(),
  })
  .passthrough();

export const DesignDoc = Base.extend({
  type: z.literal("design-doc"),
  title: z.string(),
  mode: z.enum(["builder", "startup", "intrapreneurship"]).optional(),
  generator: z.string().optional(),
}).passthrough();

// Handoff schema follows v1.12.0 context-handoff.
// `type: handoff` preferred (D9); legacy MDs without `type:` detected by
// filename + presence of session_end/next_step (see classifyArtifact).
export const Handoff = z
  .object({
    type: z.literal("handoff").optional(),
    session_end: z.string(),
    branch: z.string().optional(),
    commit_at_handoff: z.string().optional(),
    mode: z.enum(["manual", "auto"]).optional(),
    active_task: z.string().optional(),
    status: z
      .enum(["in_progress", "blocked", "ready_to_review", "done"])
      .optional(),
    completed: z.array(z.string()).default([]),
    remaining: z.array(z.string()).default([]),
    files_in_flight: z.array(z.string()).optional(),
    env: z
      .object({
        venv: z.string().optional(),
        dev_server: z.string().optional(),
        test_cmd: z.string().optional(),
      })
      .partial()
      .optional(),
    next_step: z.string(),
  })
  .passthrough();

export const Plan = Base.extend({
  type: z.literal("plan"),
  title: z.string(),
  phases: z
    .array(
      z
        .object({
          id: z.string(),
          name: z.string(),
          status: z.enum(["pending", "in_progress", "done"]),
          tasks: z.array(z.string()).optional(),
        })
        .passthrough()
    )
    .default([]),
}).passthrough();

export type DesignDocFM = z.infer<typeof DesignDoc>;
export type HandoffFM = z.infer<typeof Handoff>;
export type PlanFM = z.infer<typeof Plan>;
export type AnyFM = DesignDocFM | HandoffFM | PlanFM;

export const KNOWN_TYPES = ["design-doc", "handoff", "plan"] as const;
export type KnownType = (typeof KNOWN_TYPES)[number];

import Ajv from "ajv";

import openapi from "../../docs/openapi.json";

/**
 * Validate an answer against docs/openapi.json (OpenAPI 3.1 schemas are JSON Schema 2020-12). Error statuses are
 * checked against the documented `Problem` schema; event streams are validated frame by frame by their callers.
 */
const ajv = new Ajv({ strict: false, allErrors: true, validateFormats: false });
const ROOT_ID = "https://schemas.renti.test/openapi.json";
ajv.addSchema({ ...openapi, $id: ROOT_ID });

export const OPENAPI = openapi as unknown as {
  paths: Record<
    string,
    Record<
      string,
      {
        operationId: string;
        responses: Record<
          string,
          { content?: Record<string, { schema?: unknown }>; "x-problem-codes"?: string[] }
        >;
      }
    >
  >;
  components: { schemas: Record<string, unknown> };
};

const pointer = (path: string) => path.replace(/~/g, "~0").replace(/\//g, "~1");

export function operationKeys(): string[] {
  return Object.entries(OPENAPI.paths).flatMap(([path, item]) =>
    Object.keys(item).map((method) => `${method.toUpperCase()} ${path}`),
  );
}

export function responseOf(operation: string, status: number) {
  const [method = "", path = ""] = operation.split(" ", 2);
  return OPENAPI.paths[path]?.[method.toLowerCase()]?.responses[String(status)];
}

/** Error messages; an empty list means the body matches the schema documented for that status. */
export function validateResponse(operation: string, status: number, body: unknown): string[] {
  const [method = "", path = ""] = operation.split(" ", 2);
  const documented = responseOf(operation, status);
  if (documented === undefined) return [`${operation} does not document status ${status}`];
  if (status === 204) return body === null || body === undefined ? [] : ["204 must have no body"];
  const media = Object.keys(documented.content ?? {})[0];
  if (media === undefined || media === "text/event-stream") return [];
  const ref = `${ROOT_ID}#/paths/${pointer(path)}/${method.toLowerCase()}/responses/${status}/content/${pointer(media)}/schema`;
  const validate = ajv.getSchema(ref) ?? ajv.compile({ $ref: ref });
  return validate(body)
    ? []
    : (validate.errors ?? []).map((e) => `${e.instancePath || "/"} ${e.message ?? ""}`);
}

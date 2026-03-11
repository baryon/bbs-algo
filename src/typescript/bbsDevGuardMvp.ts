// @ts-nocheck

const {
  createHash,
  createPrivateKey,
  createPublicKey,
  generateKeyPairSync,
  sign: cryptoSign,
  verify: cryptoVerify,
} = require("crypto");

function stableJson(value: any): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJson(item)).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256Hex(data: string): string {
  return createHash("sha256").update(data, "utf8").digest("hex");
}

function normalizePosixPath(path: string): string {
  const parts = path.split("/").filter((part) => part.length > 0 && part !== ".");
  const normalizedParts: string[] = [];
  for (const part of parts) {
    if (part === "..") {
      normalizedParts.pop();
    } else {
      normalizedParts.push(part);
    }
  }
  return `/${normalizedParts.join("/")}`;
}

function pathUnderPrefix(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(`${prefix.replace(/\/$/, "")}/`);
}

export interface DbUpdateAction {
  agentId: string;
  env: string;
  table: string;
  fields: string[];
  whereScope: string;
  rowLimit: number;
  epoch: number;
  nonce: string;
  reason?: string;
}

export interface FileRemoveAction {
  agentId: string;
  path: string;
  recursive: boolean;
  epoch: number;
  nonce: string;
  reason?: string;
}

export class DbUpdatePolicy {
  readonly policyId: string;
  readonly allowedEnvs: readonly string[];
  readonly allowedTables: readonly string[];
  readonly allowedFields: readonly string[];
  readonly allowedWhereScopes: readonly string[];
  readonly maxRowLimit: number;

  constructor(args: {
    policyId: string;
    allowedEnvs: string[];
    allowedTables: string[];
    allowedFields: string[];
    allowedWhereScopes: string[];
    maxRowLimit: number;
  }) {
    this.policyId = args.policyId;
    this.allowedEnvs = [...args.allowedEnvs];
    this.allowedTables = [...args.allowedTables];
    this.allowedFields = [...args.allowedFields];
    this.allowedWhereScopes = [...args.allowedWhereScopes];
    this.maxRowLimit = args.maxRowLimit;
  }

  toJSON(): Record<string, unknown> {
    return {
      policyId: this.policyId,
      allowedEnvs: [...this.allowedEnvs],
      allowedTables: [...this.allowedTables],
      allowedFields: [...this.allowedFields],
      allowedWhereScopes: [...this.allowedWhereScopes],
      maxRowLimit: this.maxRowLimit,
    };
  }

  fingerprint(): string {
    return sha256Hex(stableJson(this.toJSON()));
  }

  evaluate(action: DbUpdateAction): string[] {
    const reasons: string[] = [];
    if (!this.allowedEnvs.includes(action.env)) {
      reasons.push("db_env_not_allowed");
    }
    if (!this.allowedTables.includes(action.table)) {
      reasons.push("db_table_not_allowed");
    }
    if (action.fields.some((field) => !this.allowedFields.includes(field))) {
      reasons.push("db_field_not_allowed");
    }
    if (!this.allowedWhereScopes.includes(action.whereScope)) {
      reasons.push("db_where_scope_not_allowed");
    }
    if (action.rowLimit <= 0) {
      reasons.push("db_row_limit_must_be_positive");
    }
    if (action.rowLimit > this.maxRowLimit) {
      reasons.push("db_row_limit_exceeds_limit");
    }
    return reasons;
  }
}

export class FileRemovePolicy {
  readonly policyId: string;
  readonly allowedPrefixes: readonly string[];
  readonly blockedPrefixes: readonly string[];
  readonly allowRecursive: boolean;

  constructor(args: {
    policyId: string;
    allowedPrefixes: string[];
    blockedPrefixes: string[];
    allowRecursive: boolean;
  }) {
    this.policyId = args.policyId;
    this.allowedPrefixes = [...args.allowedPrefixes];
    this.blockedPrefixes = [...args.blockedPrefixes];
    this.allowRecursive = args.allowRecursive;
  }

  toJSON(): Record<string, unknown> {
    return {
      policyId: this.policyId,
      allowedPrefixes: [...this.allowedPrefixes],
      blockedPrefixes: [...this.blockedPrefixes],
      allowRecursive: this.allowRecursive,
    };
  }

  fingerprint(): string {
    return sha256Hex(stableJson(this.toJSON()));
  }

  evaluate(action: FileRemoveAction): string[] {
    const reasons: string[] = [];
    const normalized = normalizePosixPath(action.path);
    if (!normalized.startsWith("/")) {
      reasons.push("file_path_must_be_absolute");
      return reasons;
    }
    if (this.blockedPrefixes.some((prefix) => pathUnderPrefix(normalized, prefix))) {
      reasons.push("file_path_blocked");
    }
    if (!this.allowedPrefixes.some((prefix) => pathUnderPrefix(normalized, prefix))) {
      reasons.push("file_path_outside_allowed_prefixes");
    }
    if (action.recursive && !this.allowRecursive) {
      reasons.push("file_recursive_remove_not_allowed");
    }
    return reasons;
  }
}

export interface SignedDevRequest {
  agentId: string;
  actionKind: string;
  publicKeyPem: string;
  policyFingerprint: string;
  actionPayload: Record<string, unknown>;
  signatureB64: string;
}

export interface SigningResult {
  ok: boolean;
  stage: "signer";
  reasons: string[];
  request: SignedDevRequest | null;
}

export interface ValidationResult {
  accepted: boolean;
  stage: "validator";
  reasons: string[];
}

export interface RegisteredDevAgent {
  publicKeyPem: string;
  dbPolicy: DbUpdatePolicy;
  filePolicy: FileRemovePolicy;
}

export function generateKeypair(): { privateKeyPem: string; publicKeyPem: string } {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  return {
    privateKeyPem: privateKey.export({ format: "pem", type: "pkcs8" }).toString(),
    publicKeyPem: publicKey.export({ format: "pem", type: "spki" }).toString(),
  };
}

function buildSigningMessage(
  actionKind: string,
  actionPayload: Record<string, unknown>,
  policyFingerprint: string,
): Buffer {
  return Buffer.from(
    stableJson({
      actionKind,
      actionPayload,
      policyFingerprint,
    }),
    "utf8",
  );
}

export class DevGuardSigner {
  private readonly agentId: string;
  private readonly privateKey: any;
  private readonly publicKeyPem: string;
  private readonly dbPolicy: DbUpdatePolicy;
  private readonly filePolicy: FileRemovePolicy;

  constructor(args: {
    agentId: string;
    privateKeyPem: string;
    publicKeyPem: string;
    dbPolicy: DbUpdatePolicy;
    filePolicy: FileRemovePolicy;
  }) {
    this.agentId = args.agentId;
    this.privateKey = createPrivateKey(args.privateKeyPem);
    this.publicKeyPem = args.publicKeyPem;
    this.dbPolicy = args.dbPolicy;
    this.filePolicy = args.filePolicy;
  }

  signDbUpdate(action: DbUpdateAction): SigningResult {
    const reasons: string[] = [];
    if (action.agentId !== this.agentId) {
      reasons.push("agent_id_mismatch");
    }
    reasons.push(...this.dbPolicy.evaluate(action));
    if (reasons.length > 0) {
      return { ok: false, stage: "signer", reasons, request: null };
    }
    const policyFingerprint = this.dbPolicy.fingerprint();
    const actionPayload = { ...action, fields: [...action.fields] };
    const signature = cryptoSign(
      null,
      buildSigningMessage("db_update", actionPayload, policyFingerprint),
      this.privateKey,
    );
    return {
      ok: true,
      stage: "signer",
      reasons: [],
      request: {
        agentId: this.agentId,
        actionKind: "db_update",
        publicKeyPem: this.publicKeyPem,
        policyFingerprint,
        actionPayload,
        signatureB64: signature.toString("base64"),
      },
    };
  }

  signFileRemove(action: FileRemoveAction): SigningResult {
    const reasons: string[] = [];
    if (action.agentId !== this.agentId) {
      reasons.push("agent_id_mismatch");
    }
    reasons.push(...this.filePolicy.evaluate(action));
    if (reasons.length > 0) {
      return { ok: false, stage: "signer", reasons, request: null };
    }
    const policyFingerprint = this.filePolicy.fingerprint();
    const actionPayload = { ...action };
    const signature = cryptoSign(
      null,
      buildSigningMessage("file_rm", actionPayload, policyFingerprint),
      this.privateKey,
    );
    return {
      ok: true,
      stage: "signer",
      reasons: [],
      request: {
        agentId: this.agentId,
        actionKind: "file_rm",
        publicKeyPem: this.publicKeyPem,
        policyFingerprint,
        actionPayload,
        signatureB64: signature.toString("base64"),
      },
    };
  }
}

export class DevGuardValidator {
  private readonly registry: Map<string, RegisteredDevAgent>;
  private readonly usedNonces = new Set<string>();

  constructor(registry: Record<string, RegisteredDevAgent>) {
    this.registry = new Map(Object.entries(registry));
  }

  validate(request: SignedDevRequest): ValidationResult {
    const registered = this.registry.get(request.agentId);
    if (!registered) {
      return { accepted: false, stage: "validator", reasons: ["unknown_agent"] };
    }

    const reasons: string[] = [];
    if (request.publicKeyPem !== registered.publicKeyPem) {
      reasons.push("public_key_not_registered");
    }

    let expectedPolicyFingerprint: string | null = null;
    let policyReasons: string[] = [];
    let nonce = "";

    if (request.actionKind === "db_update") {
      expectedPolicyFingerprint = registered.dbPolicy.fingerprint();
      const action = request.actionPayload as unknown as DbUpdateAction;
      if (action.agentId !== request.agentId) {
        reasons.push("request_agent_id_mismatch");
      }
      policyReasons = registered.dbPolicy.evaluate(action);
      nonce = action.nonce;
    } else if (request.actionKind === "file_rm") {
      expectedPolicyFingerprint = registered.filePolicy.fingerprint();
      const action = request.actionPayload as unknown as FileRemoveAction;
      if (action.agentId !== request.agentId) {
        reasons.push("request_agent_id_mismatch");
      }
      policyReasons = registered.filePolicy.evaluate(action);
      nonce = action.nonce;
    } else {
      reasons.push("unknown_action_kind");
    }

    if (
      expectedPolicyFingerprint !== null &&
      request.policyFingerprint !== expectedPolicyFingerprint
    ) {
      reasons.push("policy_fingerprint_mismatch");
    }
    if (reasons.length > 0) {
      return { accepted: false, stage: "validator", reasons };
    }

    const validSignature = cryptoVerify(
      null,
      buildSigningMessage(
        request.actionKind,
        request.actionPayload,
        request.policyFingerprint,
      ),
      createPublicKey(request.publicKeyPem),
      Buffer.from(request.signatureB64, "base64"),
    );
    if (!validSignature) {
      return { accepted: false, stage: "validator", reasons: ["invalid_signature"] };
    }
    if (policyReasons.length > 0) {
      return { accepted: false, stage: "validator", reasons: policyReasons };
    }

    const nonceKey = `${request.agentId}:${nonce}`;
    if (this.usedNonces.has(nonceKey)) {
      return { accepted: false, stage: "validator", reasons: ["replayed_nonce"] };
    }

    this.usedNonces.add(nonceKey);
    return { accepted: true, stage: "validator", reasons: [] };
  }
}

export function signWithoutPolicyCheck(args: {
  privateKeyPem: string;
  publicKeyPem: string;
  agentId: string;
  actionKind: string;
  policyFingerprint: string;
  actionPayload: Record<string, unknown>;
}): SignedDevRequest {
  const signature = cryptoSign(
    null,
    buildSigningMessage(args.actionKind, args.actionPayload, args.policyFingerprint),
    createPrivateKey(args.privateKeyPem),
  );
  return {
    agentId: args.agentId,
    actionKind: args.actionKind,
    publicKeyPem: args.publicKeyPem,
    policyFingerprint: args.policyFingerprint,
    actionPayload: args.actionPayload,
    signatureB64: signature.toString("base64"),
  };
}

export function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function demoScenarios(): Array<[string, SigningResult | ValidationResult]> {
  const dbPolicy = new DbUpdatePolicy({
    policyId: "db-staging-safe-update-v1",
    allowedEnvs: ["staging"],
    allowedTables: ["feature_flags", "task_runs"],
    allowedFields: ["enabled", "status", "updated_by"],
    allowedWhereScopes: ["id_eq", "job_id_eq"],
    maxRowLimit: 1,
  });
  const filePolicy = new FileRemovePolicy({
    policyId: "file-rm-sandbox-v1",
    allowedPrefixes: ["/workspace/sandbox", "/workspace/tmp"],
    blockedPrefixes: ["/etc", "/usr", "/bin", "/var/lib"],
    allowRecursive: false,
  });

  const trustedKeys = generateKeypair();
  const rogueKeys = generateKeypair();

  const signer = new DevGuardSigner({
    agentId: "agent_dev_bot",
    privateKeyPem: trustedKeys.privateKeyPem,
    publicKeyPem: trustedKeys.publicKeyPem,
    dbPolicy,
    filePolicy,
  });
  const validator = new DevGuardValidator({
    agent_dev_bot: {
      publicKeyPem: trustedKeys.publicKeyPem,
      dbPolicy,
      filePolicy,
    },
  });

  const validDbAction: DbUpdateAction = {
    agentId: "agent_dev_bot",
    env: "staging",
    table: "feature_flags",
    fields: ["enabled"],
    whereScope: "id_eq",
    rowLimit: 1,
    epoch: 202603111330,
    nonce: "db-001",
    reason: "toggle safe feature flag in staging",
  };
  const invalidDbAction: DbUpdateAction = {
    agentId: "agent_dev_bot",
    env: "production",
    table: "users",
    fields: ["role"],
    whereScope: "all_rows",
    rowLimit: 50,
    epoch: 202603111331,
    nonce: "db-002",
    reason: "dangerous production bulk update",
  };
  const validFileAction: FileRemoveAction = {
    agentId: "agent_dev_bot",
    path: "/workspace/sandbox/build/output.tmp",
    recursive: false,
    epoch: 202603111332,
    nonce: "fs-001",
    reason: "cleanup sandbox artifact",
  };
  const invalidFileAction: FileRemoveAction = {
    agentId: "agent_dev_bot",
    path: "/etc/passwd",
    recursive: false,
    epoch: 202603111333,
    nonce: "fs-002",
    reason: "dangerous system file remove",
  };

  const signedValidDb = signer.signDbUpdate(validDbAction);
  if (!signedValidDb.request) {
    throw new Error("expected valid db request");
  }
  const validDbResult = validator.validate(signedValidDb.request);

  const signerRejectDb = signer.signDbUpdate(invalidDbAction);

  const bypassDbRequest = signWithoutPolicyCheck({
    privateKeyPem: trustedKeys.privateKeyPem,
    publicKeyPem: trustedKeys.publicKeyPem,
    agentId: "agent_dev_bot",
    actionKind: "db_update",
    policyFingerprint: dbPolicy.fingerprint(),
    actionPayload: { ...invalidDbAction, fields: [...invalidDbAction.fields] },
  });
  const bypassDbResult = validator.validate(bypassDbRequest);

  const signedValidFile = signer.signFileRemove(validFileAction);
  if (!signedValidFile.request) {
    throw new Error("expected valid file request");
  }
  const validFileResult = validator.validate(signedValidFile.request);

  const signerRejectFile = signer.signFileRemove(invalidFileAction);

  const bypassFileRequest = signWithoutPolicyCheck({
    privateKeyPem: trustedKeys.privateKeyPem,
    publicKeyPem: trustedKeys.publicKeyPem,
    agentId: "agent_dev_bot",
    actionKind: "file_rm",
    policyFingerprint: filePolicy.fingerprint(),
    actionPayload: { ...invalidFileAction },
  });
  const bypassFileResult = validator.validate(bypassFileRequest);

  const rogueRequest = signWithoutPolicyCheck({
    privateKeyPem: rogueKeys.privateKeyPem,
    publicKeyPem: rogueKeys.publicKeyPem,
    agentId: "agent_dev_bot",
    actionKind: "file_rm",
    policyFingerprint: filePolicy.fingerprint(),
    actionPayload: { ...validFileAction },
  });
  const rogueResult = validator.validate(rogueRequest);

  const replayResult = validator.validate(signedValidFile.request);

  return [
    ["valid_db_update", validDbResult],
    ["signer_reject_db_update", signerRejectDb],
    ["validator_reject_db_policy_bypass", bypassDbResult],
    ["valid_file_rm", validFileResult],
    ["signer_reject_file_rm", signerRejectFile],
    ["validator_reject_file_policy_bypass", bypassFileResult],
    ["validator_reject_unknown_key", rogueResult],
    ["validator_reject_replay", replayResult],
  ];
}

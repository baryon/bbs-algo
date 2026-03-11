// @ts-nocheck

const {
  createHash,
  createPrivateKey,
  createPublicKey,
  generateKeyPairSync,
  sign: cryptoSign,
  verify: cryptoVerify,
} = require("crypto");

type KeyObject = any;

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

export interface PaymentAction {
  agentId: string;
  amountCents: number;
  currency: string;
  recipient: string;
  invoiceId: string;
  epoch: number;
  nonce: string;
  reason?: string;
}

export interface PaymentPolicyData {
  policyId: string;
  maxAmountCents: number;
  currency: string;
  recipientWhitelist: string[];
}

export class PaymentPolicy {
  readonly policyId: string;
  readonly maxAmountCents: number;
  readonly currency: string;
  readonly recipientWhitelist: readonly string[];

  constructor(data: PaymentPolicyData) {
    this.policyId = data.policyId;
    this.maxAmountCents = data.maxAmountCents;
    this.currency = data.currency;
    this.recipientWhitelist = [...data.recipientWhitelist];
  }

  toJSON(): PaymentPolicyData {
    return {
      policyId: this.policyId,
      maxAmountCents: this.maxAmountCents,
      currency: this.currency,
      recipientWhitelist: [...this.recipientWhitelist],
    };
  }

  fingerprint(): string {
    return sha256Hex(stableJson(this.toJSON()));
  }

  evaluate(action: PaymentAction): string[] {
    const reasons: string[] = [];
    if (action.amountCents <= 0) {
      reasons.push("amount_must_be_positive");
    }
    if (action.amountCents > this.maxAmountCents) {
      reasons.push("amount_exceeds_limit");
    }
    if (action.currency !== this.currency) {
      reasons.push("currency_not_allowed");
    }
    if (!this.recipientWhitelist.includes(action.recipient)) {
      reasons.push("recipient_not_whitelisted");
    }
    return reasons;
  }
}

export interface SignedPaymentRequest {
  agentId: string;
  publicKeyPem: string;
  policyFingerprint: string;
  action: PaymentAction;
  signatureB64: string;
}

export interface SigningResult {
  ok: boolean;
  stage: "signer";
  reasons: string[];
  request: SignedPaymentRequest | null;
}

export interface ValidationResult {
  accepted: boolean;
  stage: "validator";
  reasons: string[];
}

export interface RegisteredAgent {
  publicKeyPem: string;
  policy: PaymentPolicy;
}

export interface GeneratedKeypair {
  privateKeyPem: string;
  publicKeyPem: string;
}

export function generateKeypair(): GeneratedKeypair {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  return {
    privateKeyPem: privateKey.export({ format: "pem", type: "pkcs8" }).toString(),
    publicKeyPem: publicKey.export({ format: "pem", type: "spki" }).toString(),
  };
}

function loadPrivateKey(privateKeyPem: string): KeyObject {
  return createPrivateKey(privateKeyPem);
}

function loadPublicKey(publicKeyPem: string): KeyObject {
  return createPublicKey(publicKeyPem);
}

export function buildSigningMessage(
  action: PaymentAction,
  policyFingerprint: string,
): Buffer {
  return Buffer.from(
    stableJson({
      action,
      policyFingerprint,
    }),
    "utf8",
  );
}

export class PolicyBoundSigner {
  private readonly agentId: string;
  private readonly privateKey: KeyObject;
  private readonly publicKeyPem: string;
  private readonly policy: PaymentPolicy;

  constructor(args: {
    agentId: string;
    privateKeyPem: string;
    publicKeyPem: string;
    policy: PaymentPolicy;
  }) {
    this.agentId = args.agentId;
    this.privateKey = loadPrivateKey(args.privateKeyPem);
    this.publicKeyPem = args.publicKeyPem;
    this.policy = args.policy;
  }

  sign(action: PaymentAction): SigningResult {
    const reasons: string[] = [];
    if (action.agentId !== this.agentId) {
      reasons.push("agent_id_mismatch");
    }
    reasons.push(...this.policy.evaluate(action));
    if (reasons.length > 0) {
      return {
        ok: false,
        stage: "signer",
        reasons,
        request: null,
      };
    }

    const policyFingerprint = this.policy.fingerprint();
    const message = buildSigningMessage(action, policyFingerprint);
    const signature = cryptoSign(null, message, this.privateKey);
    return {
      ok: true,
      stage: "signer",
      reasons: [],
      request: {
        agentId: this.agentId,
        publicKeyPem: this.publicKeyPem,
        policyFingerprint,
        action,
        signatureB64: signature.toString("base64"),
      },
    };
  }
}

export class PaymentValidator {
  private readonly registry: Map<string, RegisteredAgent>;
  private readonly usedNonces = new Set<string>();

  constructor(registry: Record<string, RegisteredAgent>) {
    this.registry = new Map(Object.entries(registry));
  }

  validate(request: SignedPaymentRequest): ValidationResult {
    const registered = this.registry.get(request.agentId);
    if (!registered) {
      return {
        accepted: false,
        stage: "validator",
        reasons: ["unknown_agent"],
      };
    }

    const reasons: string[] = [];
    if (request.action.agentId !== request.agentId) {
      reasons.push("request_agent_id_mismatch");
    }
    if (request.publicKeyPem !== registered.publicKeyPem) {
      reasons.push("public_key_not_registered");
    }
    if (request.policyFingerprint !== registered.policy.fingerprint()) {
      reasons.push("policy_fingerprint_mismatch");
    }
    if (reasons.length > 0) {
      return {
        accepted: false,
        stage: "validator",
        reasons,
      };
    }

    const message = buildSigningMessage(request.action, request.policyFingerprint);
    const publicKey = loadPublicKey(request.publicKeyPem);
    const validSignature = cryptoVerify(
      null,
      message,
      publicKey,
      Buffer.from(request.signatureB64, "base64"),
    );
    if (!validSignature) {
      return {
        accepted: false,
        stage: "validator",
        reasons: ["invalid_signature"],
      };
    }

    const policyReasons = registered.policy.evaluate(request.action);
    if (policyReasons.length > 0) {
      return {
        accepted: false,
        stage: "validator",
        reasons: policyReasons,
      };
    }

    const nonceKey = `${request.agentId}:${request.action.nonce}`;
    if (this.usedNonces.has(nonceKey)) {
      return {
        accepted: false,
        stage: "validator",
        reasons: ["replayed_nonce"],
      };
    }

    this.usedNonces.add(nonceKey);
    return {
      accepted: true,
      stage: "validator",
      reasons: [],
    };
  }
}

export function signWithoutPolicyCheck(args: {
  privateKeyPem: string;
  publicKeyPem: string;
  agentId: string;
  policyFingerprint: string;
  action: PaymentAction;
}): SignedPaymentRequest {
  const message = buildSigningMessage(args.action, args.policyFingerprint);
  const signature = cryptoSign(null, message, loadPrivateKey(args.privateKeyPem));
  return {
    agentId: args.agentId,
    publicKeyPem: args.publicKeyPem,
    policyFingerprint: args.policyFingerprint,
    action: args.action,
    signatureB64: signature.toString("base64"),
  };
}

export function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function demoScenarios(): Array<[string, ValidationResult | SigningResult]> {
  const policy = new PaymentPolicy({
    policyId: "pay-200usd-whitelist-v1",
    maxAmountCents: 20_000,
    currency: "USD",
    recipientWhitelist: ["vendor_123", "vendor_456"],
  });

  const trustedKeys = generateKeypair();
  const rogueKeys = generateKeypair();

  const signer = new PolicyBoundSigner({
    agentId: "agent_payment_bot",
    privateKeyPem: trustedKeys.privateKeyPem,
    publicKeyPem: trustedKeys.publicKeyPem,
    policy,
  });

  const validator = new PaymentValidator({
    agent_payment_bot: {
      publicKeyPem: trustedKeys.publicKeyPem,
      policy,
    },
  });

  const validAction: PaymentAction = {
    agentId: "agent_payment_bot",
    amountCents: 16_850,
    currency: "USD",
    recipient: "vendor_123",
    invoiceId: "inv_001",
    epoch: 202603111200,
    nonce: "n-001",
    reason: "approved supplier payout",
  };

  const overLimitAction: PaymentAction = {
    agentId: "agent_payment_bot",
    amountCents: 24_300,
    currency: "USD",
    recipient: "vendor_123",
    invoiceId: "inv_002",
    epoch: 202603111205,
    nonce: "n-002",
    reason: "attempted over-limit payout",
  };

  const signerValid = signer.sign(validAction);
  if (!signerValid.request) {
    throw new Error("expected valid request to be signed");
  }
  const validResult = validator.validate(signerValid.request);

  const signerReject = signer.sign(overLimitAction);

  const bypassRequest = signWithoutPolicyCheck({
    privateKeyPem: trustedKeys.privateKeyPem,
    publicKeyPem: trustedKeys.publicKeyPem,
    agentId: "agent_payment_bot",
    policyFingerprint: policy.fingerprint(),
    action: overLimitAction,
  });
  const bypassResult = validator.validate(bypassRequest);

  const rogueRequest = signWithoutPolicyCheck({
    privateKeyPem: rogueKeys.privateKeyPem,
    publicKeyPem: rogueKeys.publicKeyPem,
    agentId: "agent_payment_bot",
    policyFingerprint: policy.fingerprint(),
    action: validAction,
  });
  const rogueResult = validator.validate(rogueRequest);

  const tamperedRequest: SignedPaymentRequest = {
    ...signerValid.request,
    action: {
      ...signerValid.request.action,
      recipient: "vendor_456",
      nonce: "n-003",
      reason: "payload tampered after signing",
    },
  };
  const tamperedResult = validator.validate(tamperedRequest);

  const replayResult = validator.validate(signerValid.request);

  return [
    ["valid_request", validResult],
    ["signer_side_reject", signerReject],
    ["validator_reject_policy_bypass", bypassResult],
    ["validator_reject_unknown_key", rogueResult],
    ["validator_reject_tamper", tamperedResult],
    ["validator_reject_replay", replayResult],
  ];
}

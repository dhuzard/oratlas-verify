/**
 * ORAtlas-owned fixture bootstrap for the pinned compatibility job.
 *
 * This file is copied into the pinned ORAtlas checkout and run there. Prisma
 * and ORAtlas application imports are confined to this setup phase; the
 * Python worker acceptance phase uses HTTP only.
 */
import { createHash, randomBytes } from "node:crypto";
import { writeFileSync } from "node:fs";
import { canonicalJson } from "@oratlas/contracts";
import { getPrisma } from "@oratlas/db";
import { createVerificationRun } from "../apps/web/src/lib/scientific-verification.ts";

const digest = (value: string) =>
  createHash("sha256").update(value).digest("hex");

async function main() {
  const prisma = getPrisma();
  const outputPath = process.env.ORATLAS_VERIFY_BOOTSTRAP_OUTPUT;
  if (!outputPath)
    throw new Error("ORATLAS_VERIFY_BOOTSTRAP_OUTPUT is required.");

  const verifier = await prisma.verifier.findUniqueOrThrow({
    where: { id: "oratlas-verify-demo" },
  });
  const editor = await prisma.user.findFirstOrThrow({
    where: { role: "EDITOR" },
  });
  const tokenPrefix = randomBytes(9).toString("base64url");
  const token = `oratlas_verify_${tokenPrefix}.${randomBytes(32).toString("base64url")}`;
  await prisma.verifierCredential.create({
    data: {
      verifierId: verifier.id,
      label: "oratlas-verify pinned compatibility",
      tokenPrefix,
      tokenHash: digest(token),
      scopesJson: canonicalJson(["verification:read", "verification:submit"]),
      issuedById: editor.id,
    },
  });

  const cases = [
    {
      key: "verified",
      text: "Synthetic results: t(38) = 3.12, p = 0.0034, two-sided.",
    },
    {
      key: "discrepancy",
      text: "Synthetic results: t(38) = 3.12, p = 0.2, two-sided.",
    },
    {
      key: "unverifiable",
      text: "Synthetic results: t(38) = 3.12, p = 0.0034.",
    },
  ] as const;

  const runs: Record<string, string> = {};
  for (const item of cases) {
    const publicationId = `oratlas-verify-compat-${item.key}`;
    const versionId = `${publicationId}-version`;
    const documentId = `publication-content:${publicationId}`;
    const contentSha256 = digest(item.text);
    const identitySha256 = digest(`${publicationId}:content-slot`);
    const contentJson = canonicalJson([
      {
        id: documentId,
        title: `Synthetic ${item.key} statistic`,
        role: "results",
        sourcePath: "article.md",
        publishedUrl: `https://compat.example.test/${item.key}/`,
        representation: "published-structured-text",
        text: item.text,
        sha256: contentSha256,
        sourceArtifactIdentitySha256: identitySha256,
        sourceArtifactSha256: contentSha256,
      },
    ]);
    const publication = await prisma.publication.create({
      data: {
        id: publicationId,
        stableKey: `registration:${publicationId}`,
        publicationType: "research-article",
        recordSource: "external-publication",
        identityEvidenceJson: canonicalJson({
          basis: "registration",
          registrationKey: publicationId,
        }),
        sourceLocalPublicationId: publicationId,
      },
    });
    await prisma.publicationVersion.create({
      data: {
        id: versionId,
        publicationId: publication.id,
        stableKey: `${publicationId}:v1`,
        sourceLocalPublicationId: publicationId,
        sourcesSha256: digest(`${publicationId}:v1`),
        versionLabel: "v1",
        title: `Synthetic ${item.key} statistic`,
        canonicalUrl: null,
        observedPublicationBaseUrl: `https://compat.example.test/${item.key}/`,
        adapterType: "myst",
        adapterBindingJson: canonicalJson({
          type: "myst",
          protocolVersion: "0.2.0",
          crossReferenceInventoryPath: "myst.xref.json",
          generatorName: "oratlas-verify-compatibility",
          generatorVersion: "0.1.1",
        }),
        structuralProvenance: "published-structure",
        verificationWarningsJson: canonicalJson([
          "Synthetic compatibility fixture.",
        ]),
        contentCorpusJson: contentJson,
        contentCorpusSha256: digest(contentJson),
        contentCompletenessJson: canonicalJson({
          returnedDocuments: 1,
          totalDocumentsKnown: 1,
          truncated: false,
          coverage: "complete",
        }),
        observedAt: new Date("2026-08-25T12:00:00.000Z"),
        captures: {
          create: {
            id: `${publicationId}-capture`,
            artifactKind: "published-page-data",
            artifactIdentitySha256: identitySha256,
            declaredPath: "article.md",
            observedUrl: `https://compat.example.test/${item.key}/`,
            requestedUrl: `https://compat.example.test/${item.key}/`,
            mediaType: "text/markdown",
            contentSha256,
            byteLength: Buffer.byteLength(item.text, "utf8"),
            contentBytes: item.text,
            httpProvenanceJson: canonicalJson({ synthetic: true }),
            structuralProvenance: "published-structure",
            capturedAt: new Date("2026-08-25T12:00:00.000Z"),
          },
        },
      },
    });
    const run = await createVerificationRun(
      {
        verificationProtocolId: "reported-statistic-consistency-0-1-0",
        subject: {
          type: "publication-version",
          publicationVersionId: versionId,
        },
        inputProfile: "blinded-scientific",
        inputProfileVersion: "1.0.0",
        idempotencyKey: `oratlas-verify-compat-${item.key}`,
      },
      editor.id,
    );
    runs[item.key] = run.id;
  }

  writeFileSync(outputPath, JSON.stringify({ token, runs }), {
    encoding: "utf8",
    mode: 0o600,
  });
  await prisma.$disconnect();
}

main().catch((error: unknown) => {
  console.error(
    error instanceof Error
      ? error.message
      : "ORAtlas compatibility bootstrap failed.",
  );
  process.exitCode = 1;
});

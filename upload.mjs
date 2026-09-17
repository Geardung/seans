import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { readdirSync, readFileSync } from "fs";
import { join, relative, extname } from "path";

const DIST = "dist";
const BUCKET = "e7ad1529f5f1-watchin-mokchin";
const ENDPOINT = "https://s3.ru1.storage.beget.cloud";

const MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};

const client = new S3Client({
  region: "ru1",
  endpoint: ENDPOINT,
  forcePathStyle: true,
  credentials: {
    accessKeyId: "T0R6XDXZL0C6VUFLT4DC",
    secretAccessKey: "mc06XtTMhDWlRxznQINtmXmVeXNHG4EoeBJbDcw2",
  },
});

function walk(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) files.push(...walk(full));
    else files.push(full);
  }
  return files;
}

const files = walk(DIST);
console.log(`Uploading ${files.length} files to s3://${BUCKET}/`);

for (const file of files) {
  const key = relative(DIST, file).replace(/\\/g, "/");
  const ext = extname(file).toLowerCase();
  const contentType = MIME[ext] || "application/octet-stream";

  await client.send(
    new PutObjectCommand({
      Bucket: BUCKET,
      Key: key,
      Body: readFileSync(file),
      ContentType: contentType,
    })
  );
  console.log(`  ${key} (${contentType})`);
}

console.log("Done!");

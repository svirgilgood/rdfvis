#!/usr/bin/env node
import yargs from "yargs/yargs";
import n3 from "n3";
import fs from "fs";
import path from "path";
import ns from "@semantic-arts/rdfjs/namespaces/index.js";
import DatasetExt from "rdf-ext/lib/Dataset.js";

const { Store, DataFactory } = n3;
const { namedNode } = DataFactory;

const mimeType = {
  ".trig": "application/trig",
  ".ttl": "text/turtle",
};

const prefixes = {
  owl: "http://www.w3.org/2002/07/owl#",
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  rdfs: "http://www.w3.org/2000/01/rdf-schema#",
  sh: "http://www.w3.org/ns/shacl#",
  skos: "http://www.w3.org/2004/02/skos/core#",
  xsd: "http://www.w3.org/2001/XMLSchema#",
  dcao: "https://ontologies.semanticarts.com/dcao/",
  dcas: "https://ontologies.semanticarts.com/dcas/",
  dcax: "https://ontologies.semanticarts.com/dcax/",
  gist: "https://ontologies.semanticarts.com/gist/",
  sa: "https://ontologies.semanticarts.com/SemArts/",
};

const LStore = new Store();

/**
 *
 * @param {string} value
 * @returns {string}
 */
function formatValues(value) {
  for (const dict of Object.entries(prefixes)) {
    const [prefix, namespace] = dict;
    if (value.startsWith(namespace)) {
      const localName = value.split(namespace).pop();
      return `${prefix}:${localName}`;
    }
  }
  return value;
}

/**
 * Expand known prefixes.
 *
 * @param {string} value
 * @returns {string}
 */
function expandPrefixUri(value) {
  const [prefix, ...localName] = value.split(":");
  if (prefix === "http" || prefix === "https") return value;
  const namespace = prefixes[prefix];
  if (!namespace) return value;
  return `${namespace}${localName.join(":")}`;
}

/**
 *
 * @param {string} file
 * @returns {Quad[]}
 */
function createQuadsFromFile(file) {
  const ext = path.extname(file);
  const fileContents = fs.readFileSync(file);
  const quads = deserialize(fileContents.toString(), mimeType[ext]).toQuads();
  return quads;
}

function main() {
  const options = yargs(process.argv.slice(2)).options({
    u: {
      alias: "uri",
      describe: "the uri for the main element to build the diagram from",
      type: "string",
    },
  });

  for (const file of options._) {
    const quads = createQuadsFromFile(file);
    LStore.addQuads(quads);
  }

  if (!options.uri) {
    throw new Error("You must provide an initial uri");
  }

  const headTerm = namedNode(expandPrefixUri(options.uri));
}

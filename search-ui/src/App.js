/*
 * Task 5 — Search-UI frontend for the cv-transcriptions index.
 *
 * Searchable fields (per assignment): generated_text (full-text query),
 * plus duration, age, gender and accent (facet filters on the left).
 *
 * The Elasticsearch cluster is reached through the same-origin path
 * /elasticsearch/*, which nginx (see nginx.conf) proxies to es01:9200 on the
 * internal Docker network — the cluster itself is never exposed publicly.
 */
import React from "react";
import ElasticsearchAPIConnector from "@elastic/search-ui-elasticsearch-connector";
import {
  ErrorBoundary,
  Facet,
  SearchProvider,
  SearchBox,
  Results,
  PagingInfo,
  ResultsPerPage,
  Paging,
  WithSearch
} from "@elastic/react-search-ui";
import { Layout } from "@elastic/react-search-ui-views";
import "@elastic/react-search-ui-views/lib/styles/styles.css";

const connector = new ElasticsearchAPIConnector({
  // Same-origin path proxied by nginx to http://es01:9200 (see nginx.conf).
  // For local development against a cluster on localhost use:
  //   REACT_APP_ES_HOST=http://localhost:9200 npm start
  host:
    process.env.REACT_APP_ES_HOST ||
    `${window.location.origin}/elasticsearch`,
  index: "cv-transcriptions"
});

const config = {
  apiConnector: connector,
  alwaysSearchOnInitialLoad: true,
  searchQuery: {
    search_fields: {
      generated_text: { weight: 3 }
    },
    result_fields: {
      filename: { raw: {} },
      generated_text: { snippet: { size: 300, fallback: true } },
      text: { raw: {} },
      duration: { raw: {} },
      age: { raw: {} },
      gender: { raw: {} },
      accent: { raw: {} }
    },
    facets: {
      age: { type: "value", size: 15 },
      gender: { type: "value", size: 5 },
      accent: { type: "value", size: 20 },
      duration: {
        type: "range",
        ranges: [
          { from: 0, to: 3, name: "0 – 3 s" },
          { from: 3, to: 5, name: "3 – 5 s" },
          { from: 5, to: 8, name: "5 – 8 s" },
          { from: 8, name: "8 s +" }
        ]
      }
    },
    disjunctiveFacets: ["age", "gender", "accent"]
  }
};

/* Render one search hit: ASR transcription, ground truth and metadata. */
const ResultView = ({ result }) => (
  <li className="sui-result">
    <div className="sui-result__header">
      <span
        className="sui-result__title"
        // Snippets come back from ES with <em> highlight tags.
        dangerouslySetInnerHTML={{
          __html:
            (result.generated_text && result.generated_text.snippet) ||
            (result.generated_text && result.generated_text.raw) ||
            "(no transcription)"
        }}
      />
    </div>
    <div className="sui-result__body">
      <ul className="sui-result__details">
        <li>
          <span className="sui-result__key">filename</span>{" "}
          <span className="sui-result__value">{result.filename && result.filename.raw}</span>
        </li>
        <li>
          <span className="sui-result__key">ground truth</span>{" "}
          <span className="sui-result__value">{result.text && result.text.raw}</span>
        </li>
        <li>
          <span className="sui-result__key">duration</span>{" "}
          <span className="sui-result__value">
            {result.duration && result.duration.raw != null ? `${result.duration.raw} s` : "—"}
          </span>
        </li>
        <li>
          <span className="sui-result__key">age</span>{" "}
          <span className="sui-result__value">{(result.age && result.age.raw) || "—"}</span>
        </li>
        <li>
          <span className="sui-result__key">gender</span>{" "}
          <span className="sui-result__value">{(result.gender && result.gender.raw) || "—"}</span>
        </li>
        <li>
          <span className="sui-result__key">accent</span>{" "}
          <span className="sui-result__value">{(result.accent && result.accent.raw) || "—"}</span>
        </li>
      </ul>
    </div>
  </li>
);

export default function App() {
  return (
    <SearchProvider config={config}>
      <WithSearch mapContextToProps={({ wasSearched }) => ({ wasSearched })}>
        {({ wasSearched }) => (
          <div className="App">
            <ErrorBoundary>
              <Layout
                header={
                  <SearchBox
                    inputProps={{
                      placeholder: "Search transcriptions (generated_text) …"
                    }}
                  />
                }
                sideContent={
                  <div>
                    <Facet field="duration" label="Duration" />
                    <Facet field="age" label="Age" filterType="any" />
                    <Facet field="gender" label="Gender" filterType="any" />
                    <Facet field="accent" label="Accent" filterType="any" isFilterable={true} />
                  </div>
                }
                bodyContent={<Results resultView={ResultView} />}
                bodyHeader={
                  <>
                    {wasSearched && <PagingInfo />}
                    {wasSearched && <ResultsPerPage />}
                  </>
                }
                bodyFooter={<Paging />}
              />
            </ErrorBoundary>
          </div>
        )}
      </WithSearch>
    </SearchProvider>
  );
}

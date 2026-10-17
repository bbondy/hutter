import React, {useMemo, useState} from 'react';

const MAX_BYTES = 96;
const EXAMPLES = [
  {label: 'Frequent bytes', input: 'AAAABBCD', mode: 'huffman', explanation: 'A appears four times, so this toy tree can give it a shorter code. The displayed bit total excludes a header and tree description.'},
  {label: 'Repeated pair', input: 'ABABABAB', mode: 'lz77', explanation: 'After literal A and B, the remaining six bytes can be copied from two bytes back.'},
  {label: 'Repeated triple', input: 'abcabcabc', mode: 'lz77', explanation: 'The first abc is literal; the next six bytes can be copied from three bytes back.'},
  {label: 'Overlapping run', input: 'AAAAAA', mode: 'lz77', explanation: 'After one literal A, a distance-1 match can copy the newest A repeatedly.'},
  {label: 'Next-byte context', input: 'ABABABAB', mode: 'context', explanation: 'The final B has earlier examples followed by A, so A is the toy model’s next-byte prediction.'},
  {label: 'Missing context', input: 'ABAC', mode: 'context', explanation: 'The final C has no earlier following byte in this input. This toy predictor falls back to counts for the whole input.'},
  {label: 'UTF-8 bytes', input: 'ééé', mode: 'huffman', explanation: 'Each visible é occupies two UTF-8 bytes. The model counts six bytes, not three characters.'},
];

function byteLabel(value) {
  const hex = `0x${value.toString(16).padStart(2, '0').toUpperCase()}`;
  return value >= 32 && value <= 126
    ? `${JSON.stringify(String.fromCharCode(value))} (${hex})`
    : hex;
}

function huffmanCodes(bytes) {
  const counts = new Map();
  for (const byte of bytes) {
    counts.set(byte, (counts.get(byte) || 0) + 1);
  }

  const nodes = Array.from(counts, ([symbol, count]) => ({
    count,
    minSymbol: symbol,
    symbol,
  }));
  if (nodes.length === 0) return [];

  while (nodes.length > 1) {
    nodes.sort((first, second) => first.count - second.count || first.minSymbol - second.minSymbol);
    const first = nodes.shift();
    const second = nodes.shift();
    nodes.push({
      count: first.count + second.count,
      minSymbol: Math.min(first.minSymbol, second.minSymbol),
      left: first,
      right: second,
    });
  }

  const codes = new Map();
  function visit(node, prefix) {
    if (node.symbol !== undefined) {
      codes.set(node.symbol, prefix || '0');
      return;
    }
    visit(node.left, `${prefix}0`);
    visit(node.right, `${prefix}1`);
  }
  visit(nodes[0], '');

  return Array.from(counts, ([symbol, count]) => ({symbol, count, code: codes.get(symbol)}))
    .sort((first, second) => second.count - first.count || first.symbol - second.symbol);
}

function lzTokens(bytes) {
  const tokens = [];
  let position = 0;
  while (position < bytes.length) {
    let bestLength = 0;
    let bestDistance = 0;
    const windowStart = Math.max(0, position - 16);
    for (let candidate = windowStart; candidate < position; candidate += 1) {
      const distance = position - candidate;
      let length = 0;
      while (length < 12 && position + length < bytes.length &&
        bytes[candidate + (length % distance)] === bytes[position + length]) {
        length += 1;
      }
      if (length > bestLength) {
        bestLength = length;
        bestDistance = distance;
      }
    }
    if (bestLength >= 3) {
      tokens.push({position, distance: bestDistance, length: bestLength});
      position += bestLength;
    } else {
      tokens.push({position, literal: bytes[position]});
      position += 1;
    }
  }
  return tokens;
}

function contextPrediction(bytes) {
  const transitions = new Map();
  const overall = new Map();
  for (let index = 0; index < bytes.length; index += 1) {
    const current = bytes[index];
    overall.set(current, (overall.get(current) || 0) + 1);
    if (index > 0) {
      const previous = bytes[index - 1];
      if (!transitions.has(previous)) transitions.set(previous, new Map());
      const following = transitions.get(previous);
      following.set(current, (following.get(current) || 0) + 1);
    }
  }
  const context = bytes.length ? bytes[bytes.length - 1] : null;
  const matched = context !== null ? transitions.get(context) : null;
  const counts = matched && matched.size ? matched : overall;
  const total = Array.from(counts.values()).reduce((sum, count) => sum + count, 0);
  return {
    context,
    backedOff: Boolean(context !== null && (!matched || !matched.size)),
    rows: Array.from(counts, ([symbol, count]) => ({symbol, count, probability: count / total}))
      .sort((first, second) => second.count - first.count || first.symbol - second.symbol),
  };
}

export default function CompressionLab() {
  const [input, setInput] = useState(EXAMPLES[0].input);
  const [mode, setMode] = useState('huffman');
  const encoded = useMemo(() => new TextEncoder().encode(input), [input]);
  const bytes = useMemo(() => encoded.slice(0, MAX_BYTES), [encoded]);
  const codes = useMemo(() => huffmanCodes(bytes), [bytes]);
  const tokens = useMemo(() => lzTokens(bytes), [bytes]);
  const prediction = useMemo(() => contextPrediction(bytes), [bytes]);
  const codeBits = codes.reduce((sum, row) => sum + row.count * row.code.length, 0);
  const activeExample = EXAMPLES.find((example) => example.input === input && example.mode === mode);

  return <div className="lab-shell">
    <div className="lab-controls">
      <label htmlFor="compression-lab-input">Change the input
        <textarea id="compression-lab-input" value={input} onChange={(event) => setInput(event.target.value)} spellCheck="false" />
      </label>
      <div className="lab-note">{bytes.length} byte{bytes.length === 1 ? '' : 's'} shown · {bytes.length * 8} raw bits{encoded.length > MAX_BYTES ? ` · first ${MAX_BYTES} bytes only` : ''}</div>
    </div>
    <div className="lab-presets" aria-label="Worked inputs">
      <span>Worked inputs</span>
      {EXAMPLES.map((example) => <button key={example.label} type="button" aria-pressed={activeExample === example} onClick={() => { setInput(example.input); setMode(example.mode); }}>{example.label}</button>)}
      {activeExample && <p className="lab-example-note">{activeExample.explanation}</p>}
    </div>
    <div className="lab-tabs" aria-label="Compression idea">
      {[
        ['huffman', 'Short codes'],
        ['lz77', 'Back-references'],
        ['context', 'Next-byte prediction'],
      ].map(([value, label]) => <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)}>{label}</button>)}
    </div>
    <div className="lab-panel" aria-live="polite">
      {mode === 'huffman' && <>
        <h3>Give common bytes shorter codes</h3>
        <p>A Huffman tree for just these input bytes yields {codeBits} data bits, versus {bytes.length * 8} raw bits. A real archive also has a header and a way to reproduce the model.</p>
        {codes.length ? <table><thead><tr><th>Byte</th><th>Count</th><th>Code</th><th>Data bits</th></tr></thead><tbody>{codes.map((row) => <tr key={row.symbol}><td>{byteLabel(row.symbol)}</td><td>{row.count}</td><td><code>{row.code}</code></td><td>{row.count * row.code.length}</td></tr>)}</tbody></table> : <p>Enter some text to build a tree.</p>}
        <p className="lab-note">The repository’s Huffman codec starts with all 256 byte counts at one and adapts across blocks. This toy tree uses only the displayed input.</p>
      </>}
      {mode === 'lz77' && <>
        <h3>Point back to repeated bytes</h3>
        <p>The toy encoder looks back up to 16 bytes and writes a match when at least three bytes repeat. Distance is how far back the copy starts; length is how many bytes to copy.</p>
        {tokens.length ? <table><thead><tr><th>Input offset</th><th>Token</th><th>Meaning</th></tr></thead><tbody>{tokens.map((token) => <tr key={token.position}><td>{token.position}</td><td><code>{token.literal !== undefined ? `literal ${byteLabel(token.literal)}` : `match (${token.distance}, ${token.length})`}</code></td><td>{token.literal !== undefined ? 'Write this byte' : 'Copy from earlier output'}</td></tr>)}</tbody></table> : <p>Enter some text to make tokens.</p>}
        <p className="lab-note">The Rust codec uses a 4 KiB window and can emit matches up to 255 bytes. This small window makes the demonstration easier to inspect.</p>
      </>}
      {mode === 'context' && <>
        <h3>What might follow the last byte?</h3>
        <p>{prediction.context === null ? 'Enter a prefix to make a prediction.' : <>The last byte is <code>{byteLabel(prediction.context)}</code>. {prediction.backedOff ? 'This input has no earlier example after that byte, so the toy model falls back to overall counts.' : 'The table counts bytes that followed it earlier in the input.'}</>}</p>
        {prediction.rows.length > 0 && <table><thead><tr><th>Possible next byte</th><th>Seen</th><th>Share of these observations</th></tr></thead><tbody>{prediction.rows.map((row) => <tr key={row.symbol}><td>{byteLabel(row.symbol)}</td><td>{row.count}</td><td>{(row.probability * 100).toFixed(1)}%</td></tr>)}</tbody></table>}
        <p className="lab-note">Real PPM uses escape events, unseen-symbol handling, and multiple context orders. These raw counts are just the first intuition.</p>
      </>}
    </div>
  </div>;
}

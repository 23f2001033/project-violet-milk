/**
 * ORGAN 8 — Flag Agent (unsupervised ML).  Owner: FE2
 *
 * Renders Isolation Forest + DBSCAN findings, and is designed so they can
 * never be mistaken for a risk assessment. No 0–100 number, no LOW/HIGH badge,
 * no red — the visual language of the Risk Inspector is deliberately withheld.
 * A finding here says "unlike its peers", never "guilty".
 *
 * The advisory banner is not boilerplate: on this dataset the model flags the
 * complainant, because they moved the largest single amount. That is the whole
 * argument for keeping ML off the score, so it is shown, not hidden.
 */

import { Empty, short } from '../components/ui'

function ClusterChip({ id, size }) {
  const noise = id === '-1'
  return (
    <div className="bg-panel2 rounded px-2.5 py-1.5 min-w-[74px]">
      <div className="label text-[9px]">
        {noise ? 'Unclustered' : `Cluster ${id}`}
      </div>
      <div className="font-mono text-sm text-slate-300">{size}</div>
    </div>
  )
}

export default function FlagAgent({ anomaly, nodes = [], onSelect, selected }) {
  if (!anomaly) return <Empty>No anomaly analysis available.</Empty>

  const labelFor = (id) =>
    nodes.find((n) => n.id === id)?.label ?? 'Unlabelled'

  if (!anomaly.trained) {
    return (
      <div className="p-5 max-w-2xl">
        <div className="label mb-2">Flag Agent · not run</div>
        <p className="text-[12px] text-slate-400 leading-relaxed">
          {anomaly.reason}
        </p>
        <p className="text-[11px] text-slate-600 mt-3 leading-relaxed">
          Reporting model output on too few samples would be describing noise.
          The deterministic risk engine is unaffected and has scored every
          entity as normal.
        </p>
      </div>
    )
  }

  return (
    <div className="p-5 space-y-5 overflow-y-auto h-full">
      <div className="rounded border border-amber-500/40 bg-amber-500/10 p-3">
        <div className="text-[10px] font-bold uppercase tracking-wider
                        text-amber-300 mb-1">
          Secondary lead signal — not a risk score
        </div>
        <p className="text-[11px] text-slate-300 leading-relaxed">
          {anomaly.advisory}
        </p>
      </div>

      <div className="flex flex-wrap gap-3 items-start">
        <div className="bg-panel2 rounded px-2.5 py-1.5">
          <div className="label text-[9px]">Method</div>
          <div className="font-mono text-[11px] text-slate-300">
            {anomaly.method}
          </div>
        </div>
        <div className="bg-panel2 rounded px-2.5 py-1.5">
          <div className="label text-[9px]">Version</div>
          <div className="font-mono text-[11px] text-slate-300">
            {anomaly.version}
          </div>
        </div>
        {Object.entries(anomaly.cluster_sizes ?? {}).map(([id, size]) => (
          <ClusterChip key={id} id={id} size={size} />
        ))}
      </div>

      <div>
        <div className="label mb-2">
          Behavioural outliers · {anomaly.findings.length}
        </div>

        {anomaly.findings.length === 0 ? (
          <p className="text-[11px] text-slate-600">
            No entity in this case behaves unlike its peers.
          </p>
        ) : (
          <ul className="space-y-2">
            {anomaly.findings.map((f) => (
              <li
                key={f.node_id}
                onClick={() => onSelect?.(f.node_id)}
                className={`cursor-pointer rounded border border-edge px-3 py-2.5
                  transition-colors ${
                    selected === f.node_id ? 'bg-violet/15' : 'hover:bg-panel2'
                  }`}
              >
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="font-mono text-[11px] text-slate-300">
                    {short(f.node_id, 14, 6)}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {labelFor(f.node_id)}
                  </span>
                  <span className="ml-auto font-mono text-[10px] text-slate-600">
                    {f.cluster === -1 ? 'unclustered' : `cluster ${f.cluster}`}
                    {' · '}
                    {f.score.toFixed(3)}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                  {f.explanation}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="pt-3 border-t border-edge text-[10px] text-slate-600
                      leading-relaxed max-w-2xl">
        <strong className="text-slate-500">Why unsupervised.</strong>{' '}
        Gradient-boosted classifiers need wallets labelled fraud / not-fraud to
        learn from. No such labelled set exists for this case, and building one
        ourselves would mean the model merely rediscovers our own labels.
        Isolation Forest and DBSCAN require no labels — they describe the shape
        of the data actually present.
        <br />
        <br />
        <strong className="text-slate-500">Honest limitation.</strong> On a
        graph this small, this is descriptive statistics with a fashionable
        name. Its value grows with the number of wallets; here it largely
        confirms what the deterministic rules already found.
      </div>
    </div>
  )
}

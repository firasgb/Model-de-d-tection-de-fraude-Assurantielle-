import { useState, useEffect } from 'react'

// Mapping groupes => indicateurs (code, label, default weight)
const INDICATOR_GROUPS: Record<string, Array<{ code: string; label: string; default: number }>> = {
  financial: [
    { code: "FIN_3STD", label: "Montant > µ+3σ (extrême)", default: 25 },
    { code: "FIN_3STD_PLUS", label: "Montant > µ+3σ ET >5× moyenne", default: 3 },
    { code: "FIN_RATIO_5X", label: "Montant > 5× la moyenne", default: 14 },
    { code: "FIN_RATIO_3X", label: "Montant > 3× la moyenne", default: 10 },
    { code: "FIN_RATIO_2X", label: "Montant > 2× la moyenne", default: 7 },
    { code: "FIN_RATIO_15X", label: "Montant > 1.5× la moyenne", default: 4 },
    { code: "FIN_10X_PRIME", label: "Montant > 10× la prime contrat", default: 20 },
    { code: "FIN_5X_PRIME", label: "Montant > 5× la prime", default: 10 },
    { code: "FIN_3X_PRIME", label: "Montant > 3× la prime", default: 6 },
    { code: "FIN_EXPERT_COUT", label: "Coût expert > 1.5× moyenne", default: 8 },
    { code: "FIN_AGE_MONTANT", label: "Véhicule >10 ans + montant élevé", default: 6 },
    { code: "FIN_PV_RATIO", label: "Montant > 2.5× moyenne point de vente", default: 5 },
  ],
  temporal: [
    { code: "TMP_15J", label: "Déclaration > 15j après survenance", default: 18 },
    { code: "TMP_7J_EFFET", label: "Sinistre < 7j après prise d'effet", default: 28 },
    { code: "TMP_7J_EXP", label: "Sinistre < 7j avant expiration", default: 18 },
    { code: "TMP_NUIT", label: "Sinistre entre 0h-5h", default: 8 },
    { code: "TMP_WEEKEND", label: "Sinistre samedi/dimanche", default: 5 },
    { code: "TMP_CLUSTER_VEH", label: "Cluster temporel véhicule (≤30j)", default: 7 },
    { code: "TMP_CLUSTER_CLI", label: "Cluster temporel assuré (≤30j)", default: 7 },
  ],
  frequency: [
    { code: "FRQ_7", label: "≥ 7 sinistres/12 mois", default: 25 },
    { code: "FRQ_3", label: "> 3 sinistres/12 mois", default: 16 },
    { code: "FRQ_VEH5", label: "≥ 5 sinistres sur véhicule", default: 12 },
    { code: "FRQ_VEH3", label: "≥ 3 sinistres sur véhicule", default: 8 },
    { code: "FRQ_VEH2", label: "≥ 2 sinistres sur véhicule", default: 5 },
    { code: "FRQ_AVENANTS", label: "> 2 avenants sur contrat", default: 7 },
    { code: "FRQ_AVENANT_RECENT", label: "Avenant < 30j avant sinistre", default: 12 },
    // FRQ_VELOCITE: dynamique, non modifiable
  ],
  network: [
    { code: "NET_FRONTIERE", label: "Sinistre proche frontière", default: 10 },
    { code: "NET_ADVERSE", label: "Tiers adverse récurrent", default: 10 },
    { code: "NET_TEMOIN", label: "Témoin fréquent (>3 sinistres)", default: 7 },
    { code: "NET_EXPERT_VEH", label: "Expert + véhicule répétés", default: 4 },
    { code: "NET_GARAGE", label: "Garage > 80% remplacement", default: 5 },
    { code: "NET_LIEU", label: "Lieu de sinistre récurrent", default: 4 },
    { code: "NET_COMBO_JOB", label: "Combo job-marque très fréquent", default: 3 },
  ],
  driver: [
    { code: "DRV_NOTE_TF", label: "Note conducteur < 3/10", default: 4 },
    { code: "DRV_NOTE_F", label: "Note conducteur < 5/10", default: 2 },
    { code: "DRV_KM", label: "Kilométrage annuel > 30 000 km", default: 2 },
    { code: "DRV_DIST_SIN", label: "Sinistre > 30 km du domicile", default: 2 },
    { code: "DRV_DIST_TRV", label: "Travail très éloigné domicile", default: 1 },
  ],
  profile: [
    { code: "PRF_JOB", label: "Profession à risque (taxi, transport)", default: 2 },
    { code: "PRF_USAGE", label: "Contrat usage taxi/location", default: 1 },
  ],
}

interface IndicatorWeightsEditorProps {
  initialWeights: Record<string, number>
  onSave: (weights: Record<string, number>) => void
  onError?: (error: string) => void
}

const IndicatorWeightsEditor = ({ initialWeights, onSave, onError }: IndicatorWeightsEditorProps) => {
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(Object.keys(INDICATOR_GROUPS)))
  const [searchTerm, setSearchTerm] = useState("")
  const [errors, setErrors] = useState<string[]>([])
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    // Initialiser avec les poids fournis, ou les défaut si non fourni
    const initial: Record<string, number> = {}
    Object.values(INDICATOR_GROUPS).flat().forEach(ind => {
      initial[ind.code] = initialWeights[ind.code] ?? ind.default
    })
    setWeights(initial)
  }, [initialWeights])

  const handleChange = (code: string, value: number) => {
    setWeights(prev => ({ ...prev, [code]: value }))
    setIsDirty(true)
  }

  const toggleGroup = (group: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })
  }

  const validate = (): boolean => {
    const newErrors: string[] = []
    // Pas de validation totale, juste des bornes
    setErrors(newErrors)
    if (onError && newErrors.length > 0) {
      onError(newErrors.join(', '))
    }
    return newErrors.length === 0
  }

  const handleSave = () => {
    if (validate()) {
      onSave(weights)
      setIsDirty(false)
    }
  }

  // Filtrer les indicateurs selon recherche
  const filteredGroups: Record<string, typeof INDICATOR_GROUPS[0]> = {}
  Object.entries(INDICATOR_GROUPS).forEach(([group, indicators]) => {
    const matches = indicators.filter(ind =>
      ind.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ind.code.toLowerCase().includes(searchTerm.toLowerCase())
    )
    if (matches.length > 0) {
      filteredGroups[group] = matches
    }
  })

  const totalIndicators = Object.values(INDICATOR_GROUPS).flat().length
  const modifiedCount = Object.entries(weights).filter(([code, val]) => {
    const def = Object.values(INDICATOR_GROUPS).flat().find(i => i.code === code)?.default
    return def !== undefined && val !== def
  }).length

  return (
    <div className="space-y-4 p-4 border rounded-lg bg-white">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Poids des Indicateurs Individuels</h3>
        <div className="text-sm text-gray-600">
          {modifiedCount} / {totalIndicators} modifiés
        </div>
      </div>

      {/* Recherche */}
      <div className="relative">
        <input
          type="text"
          placeholder="Rechercher un indicateur..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
      </div>

      {/* Groupes */}
      {Object.entries(filteredGroups).map(([group, indicators]) => (
        <div key={group} className="border rounded-lg overflow-hidden">
          <button
            onClick={() => toggleGroup(group)}
            className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex justify-between items-center font-medium text-gray-700"
          >
            <span className="capitalize">{group} ({indicators.length} indicateurs)</span>
            <span className="transform transition-transform" style={{
              transform: expandedGroups.has(group) ? 'rotate(90deg)' : 'rotate(0deg)'
            }}>▶</span>
          </button>

          {expandedGroups.has(group) && (
            <div className="p-4 space-y-3 bg-white">
              {indicators.map(ind => (
                <div key={ind.code} className="flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800 truncate" title={ind.label}>
                      {ind.label}
                    </div>
                    <div className="text-xs text-gray-500 font-mono">{ind.code}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0"
                      max="30"
                      step="1"
                      value={weights[ind.code] ?? ind.default}
                      onChange={(e) => handleChange(ind.code, parseInt(e.target.value))}
                      className="w-32 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                    />
                    <div className="w-16 text-right">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={weights[ind.code] ?? ind.default}
                        onChange={(e) => handleChange(ind.code, parseInt(e.target.value) || 0)}
                        className="w-16 px-2 py-1 border rounded text-sm text-center"
                      />
                    </div>
                    <div className="w-12 text-sm text-gray-500 text-right">
                      déf: {ind.default}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {Object.keys(filteredGroups).length === 0 && (
        <div className="text-center py-8 text-gray-500">
          Aucun indicateur ne correspond à "{searchTerm}"
        </div>
      )}

      {/* Info */}
      <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
        <strong>Note:</strong> Les modifications affectent le score heuristique de tous les sinistres.
        Les valeurs par défaut sont basées sur l'expertise métier v3.14.1.
      </div>

      {/* Bouton */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={!isDirty}
          className={`px-4 py-2 rounded font-medium transition-colors ${
            isDirty
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          Appliquer les poids
        </button>
      </div>
    </div>
  )
}

export default IndicatorWeightsEditor

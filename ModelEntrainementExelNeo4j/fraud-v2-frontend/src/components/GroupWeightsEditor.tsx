import { useState, useEffect } from 'react'

interface GroupWeights {
  financial: number
  temporal: number
  frequency: number
  network: number
  driver: number
  profile: number
}

interface GroupWeightsEditorProps {
  initialWeights: GroupWeights
  onSave: (weights: GroupWeights) => void
  onError?: (error: string) => void
}

const GROUP_LABELS: Record<string, string> = {
  financial: "Financier (max 35)",
  temporal: "Temporel (max 35)",
  frequency: "Fréquence (max 30)",
  network: "Réseau (max 22)",
  driver: "Conducteur (max 8)",
  profile: "Profil (max 1)",
}

const GROUP_COLORS: Record<string, string> = {
  financial: "bg-green-500",
  temporal: "bg-blue-500",
  frequency: "bg-purple-500",
  network: "bg-orange-500",
  driver: "bg-yellow-500",
  profile: "bg-red-500",
}

const GroupWeightsEditor = ({ initialWeights, onSave, onError }: GroupWeightsEditorProps) => {
  const DEFAULT_WEIGHTS: GroupWeights = { financial: 35, temporal: 28, frequency: 20, network: 10, driver: 6, profile: 1 }
  const [weights, setWeights] = useState<GroupWeights>({ ...DEFAULT_WEIGHTS, ...initialWeights })
  const [errors, setErrors] = useState<string[]>([])
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    setWeights(prev => ({ ...prev, ...initialWeights }))
  }, [initialWeights])

  const MAX_VALUES = {
    financial: 35,
    temporal: 35,
    frequency: 30,
    network: 22,
    driver: 8,
    profile: 1,
  }

  const validateWeights = (weightsToValidate: GroupWeights): boolean => {
    const newErrors: string[] = []

    const total = Object.values(weightsToValidate).reduce((sum, v) => sum + v, 0)
    if (total !== 100) {
      newErrors.push(`La somme des poids doit être 100 (actuel: ${total})`)
    }

    for (const [group, maxVal] of Object.entries(MAX_VALUES)) {
      const value = weightsToValidate[group as keyof GroupWeights]
      if (value > maxVal) {
        newErrors.push(`${GROUP_LABELS[group]}: ${value} > max ${maxVal}`)
      }
      if (value < 0) {
        newErrors.push(`${GROUP_LABELS[group]}: poids négatif interdit`)
      }
    }

    setErrors(newErrors)
    return newErrors.length === 0
  }

  const validate = (): boolean => {
    const newErrors: string[] = []
    const total = Object.values(weights).reduce((sum, v) => sum + v, 0)
    if (total !== 100) {
      newErrors.push(`La somme des poids doit être 100 (actuel: ${total})`)
    }

    for (const [group, maxVal] of Object.entries(MAX_VALUES)) {
      const value = weights[group as keyof GroupWeights]
      if (value > maxVal) {
        newErrors.push(`${GROUP_LABELS[group]}: ${value} > max ${maxVal}`)
      }
      if (value < 0) {
        newErrors.push(`${GROUP_LABELS[group]}: poids négatif interdit`)
      }
    }

    if (onError && newErrors.length > 0) {
      onError(newErrors.join(', '))
    }
    setErrors(newErrors)
    return newErrors.length === 0
  }

  const handleChange = (group: keyof GroupWeights, value: number) => {
    setWeights(prev => ({ ...prev, [group]: value }))
    setIsDirty(true)
  }

  const handleSave = () => {
    if (validate()) {
      onSave(weights)
      setIsDirty(false)
    }
  }

  const total = Object.values(weights).reduce((sum, v) => sum + v, 0)

  useEffect(() => {
    validateWeights(weights)
  }, [weights])
  const totalColor = total === 100 ? 'text-green-600' : total > 100 ? 'text-red-600' : 'text-orange-600'

  return (
    <div className="space-y-4 p-4 border rounded-lg bg-white">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Poids des Groupes d'Indicateurs</h3>
        <div className={`font-bold text-lg ${totalColor}`}>
          Total: {total} / 100
        </div>
      </div>

      {Object.entries(weights).map(([group, value]) => (
        <div key={group} className="space-y-2">
          <div className="flex justify-between items-center">
            <label className="text-sm font-medium text-gray-700">
              {GROUP_LABELS[group] || group}
            </label>
            <span className="font-mono text-lg font-bold" style={{ color: GROUP_COLORS[group]?.replace('bg-', 'text-').replace('500', '600') || '#000' }}>
              {value}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max={MAX_VALUES[group as keyof typeof MAX_VALUES]}
            step="1"
            value={value}
            onChange={(e) => handleChange(group as keyof GroupWeights, parseInt(e.target.value))}
            className={`w-full h-3 rounded-lg appearance-none cursor-pointer ${GROUP_COLORS[group]}`}
            style={{
              background: `linear-gradient(to right, ${GROUP_COLORS[group]?.replace('bg-', '#')?.replace('500', '400') || '#ccc'} 0%, ${GROUP_COLORS[group]?.replace('bg-', '#')?.replace('500', '400') || '#ccc'} ${(value / MAX_VALUES[group as keyof typeof MAX_VALUES]) * 100}%, #e5e7eb ${(value / MAX_VALUES[group as keyof typeof MAX_VALUES]) * 100}%, #e5e7eb 100%)`
            }}
          />
          <div className="flex justify-between text-xs text-gray-500">
            <span>0</span>
            <span>max {MAX_VALUES[group as keyof typeof MAX_VALUES]}</span>
          </div>
        </div>
      ))}

      {/* Erreurs de validation */}
      {errors.length > 0 && (
        <div className="p-3 bg-red-50 border border-red-200 rounded">
          <p className="text-sm text-red-700 font-medium">Erreurs de validation :</p>
          <ul className="list-disc list-inside text-sm text-red-600 mt-1">
            {errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Info */}
      <div className="p-3 bg-blue-50 border border-blue-200 rounded">
        <p className="text-sm text-blue-700">
          <strong>Note:</strong> La somme des 6 poids doit être exactement 100.
          Ces poids déterminent l'importance de chaque groupe dans le score final.
        </p>
      </div>

      {/* Bouton sauvegarder */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={!isDirty || errors.length > 0}
          className={`px-4 py-2 rounded font-medium transition-colors ${
            isDirty && errors.length === 0
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

export default GroupWeightsEditor

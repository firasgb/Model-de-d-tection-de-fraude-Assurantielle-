import { useState, useEffect } from 'react'

interface Thresholds {
  normal_max: number
  suspect_min: number
  frauduleux: number
}

interface ThresholdEditorProps {
  initialThresholds: Thresholds
  onSave: (thresholds: Thresholds) => void
  onError?: (error: string) => void
}

const ThresholdEditor = ({ initialThresholds, onSave, onError }: ThresholdEditorProps) => {
  const [thresholds, setThresholds] = useState<Thresholds>({
    normal_max: 40,
    suspect_min: 50,
    frauduleux: 70,
    ...initialThresholds,
  })
  const [errors, setErrors] = useState<string[]>([])
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    setThresholds(prev => ({ ...prev, ...initialThresholds }))
  }, [initialThresholds])

  const validate = (): boolean => {
    const newErrors: string[] = []

    if (thresholds.normal_max >= thresholds.suspect_min) {
      newErrors.push("Seuil normal_max doit être strictement inférieur à suspect_min")
    }
    if (thresholds.suspect_min >= thresholds.frauduleux) {
      newErrors.push("Seuil suspect_min doit être strictement inférieur à frauduleux")
    }
    if (thresholds.normal_max < 0 || thresholds.normal_max > 49.99) {
      newErrors.push("normal_max doit être entre 0 et 49.99")
    }
    if (thresholds.suspect_min < 50 || thresholds.suspect_min > 70) {
      newErrors.push("suspect_min doit être entre 50 et 70")
    }
    if (thresholds.frauduleux < 70 || thresholds.frauduleux > 100) {
      newErrors.push("frauduleux doit être entre 70 et 100")
    }

    setErrors(newErrors)
    if (onError && newErrors.length > 0) {
      onError(newErrors.join(', '))
    }
    return newErrors.length === 0
  }

  const handleChange = (field: keyof Thresholds, value: number) => {
    setThresholds(prev => ({ ...prev, [field]: value }))
    setIsDirty(true)
    // Validation en temps réel pour feedback immédiat
    setTimeout(() => validate(), 0)
  }

  const handleSave = () => {
    if (validate()) {
      onSave(thresholds)
      setIsDirty(false)
    }
  }

  const errorForField = (field: keyof Thresholds): boolean => {
    const t = thresholds
    if (field === 'normal_max' && t.normal_max >= t.suspect_min) return true
    if (field === 'suspect_min' && (t.suspect_min <= t.normal_max || t.suspect_min >= t.frauduleux)) return true
    if (field === 'frauduleux' && t.frauduleux <= t.suspect_min) return true
    return false
  }

  return (
    <div className="space-y-6 p-4 border rounded-lg bg-white">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">Seuils de Classification</h3>

      {/* Normal / Suspect */}
      <div className={errorForField('normal_max') ? 'ring-2 ring-red-300 rounded-lg p-2' : ''}>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Normal max (score {'<'} suspect_min): <span className="font-mono text-blue-600">{thresholds.normal_max.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min="0"
          max="49.99"
          step="0.01"
          value={thresholds.normal_max}
          onChange={(e) => handleChange('normal_max', parseFloat(e.target.value))}
          className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${errorForField('normal_max') ? 'bg-red-200' : 'bg-blue-200'}`}
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0</span>
          <span>49.99</span>
        </div>
      </div>

      {/* Suspect min */}
      <div className={errorForField('suspect_min') ? 'ring-2 ring-red-300 rounded-lg p-2' : ''}>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Suspect min (score ≥): <span className="font-mono text-orange-600">{thresholds.suspect_min.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min="50"
          max="70"
          step="0.01"
          value={thresholds.suspect_min}
          onChange={(e) => handleChange('suspect_min', parseFloat(e.target.value))}
          className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${errorForField('suspect_min') ? 'bg-red-200' : 'bg-orange-200'}`}
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>50</span>
          <span>70</span>
        </div>
      </div>

      {/* Frauduleux */}
      <div className={errorForField('frauduleux') ? 'ring-2 ring-red-300 rounded-lg p-2' : ''}>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {"Fraude (score >): "}
          <span className="font-mono text-red-600">{thresholds.frauduleux.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min="70"
          max="100"
          step="0.1"
          value={thresholds.frauduleux}
          onChange={(e) => handleChange('frauduleux', parseFloat(e.target.value))}
          className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${errorForField('frauduleux') ? 'bg-red-400' : 'bg-red-200'}`}
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>70</span>
          <span>100</span>
        </div>
      </div>

      {/* Vue actuelle */}
      <div className="mt-4 p-3 bg-gray-50 rounded border">
        <p className="text-sm font-medium text-gray-700 mb-2">Classification actuelle :</p>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 bg-green-100 rounded">
            <div className="text-xs text-green-800">NORMAL</div>
            <div className="text-sm font-bold text-green-900">0 – {thresholds.normal_max.toFixed(0)}</div>
          </div>
          <div className="p-2 bg-orange-100 rounded">
            <div className="text-xs text-orange-800">SUSPECT</div>
            <div className="text-sm font-bold text-orange-900">{thresholds.suspect_min.toFixed(0)} – {thresholds.frauduleux.toFixed(0)}</div>
          </div>
          <div className="p-2 bg-red-100 rounded">
            <div className="text-xs text-red-800">FRAUDULEUX</div>
            <div className="text-sm font-bold text-red-900">{'>'} {thresholds.frauduleux.toFixed(0)}</div>
          </div>
        </div>
      </div>

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
          Appliquer les seuils
        </button>
      </div>
    </div>
  )
}

export default ThresholdEditor

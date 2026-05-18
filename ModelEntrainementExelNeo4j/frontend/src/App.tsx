import { useState, useEffect } from 'react'
import { Shield, AlertTriangle, CheckCircle, FileText, Brain, Activity, Database } from 'lucide-react'

interface Prediction {
  sinistre_id: number
  score_suspicion: number
  statut_fraude: string
  niveau_risque: string
  features_anormales: any[]
  explication: string
}

interface Indicator {
  nom: string
  description: string
  importance: number
  type: string
}

interface Sinistre {
  index: number
  NUM_SINISTRE: string
  IMMATRICULATION: string
  DATE_SURVENANCE: string
  TOTALREGLEMENT: number
  STATUS: string
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [view, setView] = useState<'dashboard' | 'sinistres' | 'detail'>('dashboard')
  const [sinistres, setSinistres] = useState<Sinistre[]>([])
  const [selectedSinistre, setSelectedSinistre] = useState<Prediction | null>(null)
  const [indicators, setIndicators] = useState<Indicator[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      // Charger les sinistres
      const res = await fetch(`${API_URL}/sinistres?limit=100`)
      const data = await res.json()
      setSinistres(data.sinistres || [])

      // Charger les indicateurs découverts
      try {
        const indRes = await fetch(`${API_URL}/indicators`)
        const indData = await indRes.json()
        setIndicators(indData.indicators || [])
      } catch {
        console.log('API backend non disponible')
      }
    } catch (e) {
      setError('Impossible de se connecter au backend. Assurez-vous que le serveur est démarré.')
    } finally {
      setLoading(false)
    }
  }

  const analyzeSinistre = async (id: number) => {
    try {
      const res = await fetch(`${API_URL}/predict/${id}`)
      const data = await res.json()
      setSelectedSinistre(data)
      setView('detail')
    } catch {
      alert('Erreur lors de lanalyse')
    }
  }

  const getScoreColor = (score: number) => {
    if (score < 30) return 'text-green-600 bg-green-100'
    if (score < 70) return 'text-orange-600 bg-orange-100'
    return 'text-red-600 bg-red-100'
  }

  const getStatutBadge = (statut: string) => {
    if (statut === 'frauduleux') return 'bg-red-500 text-white'
    if (statut === 'suspect') return 'bg-orange-500 text-white'
    return 'bg-green-500 text-white'
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-600 border-t-transparent mx-auto mb-4"></div>
          <p className="text-gray-600">Chargement...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md p-8 bg-white rounded-xl shadow-lg">
          <AlertTriangle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">Connexion impossible</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button onClick={loadData} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Réessayer
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-gradient-to-br from-blue-600 to-purple-600 p-3 rounded-xl">
                <Brain className="h-8 w-8 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Détection Fraude Auto</h1>
                <p className="text-sm text-gray-500">Le modèle découvre seul les patterns</p>
              </div>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => setView('dashboard')}
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  view === 'dashboard' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Activity className="h-4 w-4 inline mr-2" />
                Tableau de Bord
              </button>
              <button
                onClick={() => setView('sinistres')}
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  view === 'sinistres' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <FileText className="h-4 w-4 inline mr-2" />
                Sinistres
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {view === 'dashboard' && (
          <div className="space-y-8">
            {/* Hero */}
            <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-8 text-white">
              <div className="flex items-center space-x-4 mb-4">
                <Shield className="h-12 w-12" />
                <div>
                  <h2 className="text-2xl font-bold">Système de Détection Automatique</h2>
                  <p className="opacity-90">Le modèle apprend seul des données Excel</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                <div className="bg-white/20 rounded-lg p-4">
                  <Database className="h-6 w-6 mb-2" />
                  <p className="text-sm opacity-90">Données analysées</p>
                  <p className="text-2xl font-bold">{sinistres.length}+ sinistres</p>
                </div>
                <div className="bg-white/20 rounded-lg p-4">
                  <Brain className="h-6 w-6 mb-2" />
                  <p className="text-sm opacity-90">Indicateurs découverts</p>
                  <p className="text-2xl font-bold">{indicators.length}</p>
                </div>
                <div className="bg-white/20 rounded-lg p-4">
                  <Activity className="h-6 w-6 mb-2" />
                  <p className="text-sm opacity-90">Apprentissage</p>
                  <p className="text-2xl font-bold">Non supervisé</p>
                </div>
              </div>
            </div>

            {/* Indicateurs découverts */}
            {indicators.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                  <Brain className="h-5 w-5 mr-2 text-purple-600" />
                  Indicateurs Découverts par le Modèle
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {indicators.slice(0, 9).map((ind, i) => (
                    <div key={i} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          ind.type === 'financier' ? 'bg-green-100 text-green-700' :
                          ind.type === 'temporel' ? 'bg-blue-100 text-blue-700' :
                          ind.type === 'réseau' ? 'bg-purple-100 text-purple-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {ind.type}
                        </span>
                        <span className="text-sm font-bold text-gray-700">
                          {(ind.importance * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="font-medium text-gray-900">{ind.nom}</p>
                      <p className="text-sm text-gray-500 mt-1">{ind.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Commencer</h3>
              <button
                onClick={() => setView('sinistres')}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition"
              >
                Analyser les Sinistres
              </button>
            </div>
          </div>
        )}

        {view === 'sinistres' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">Liste des Sinistres</h2>
              <span className="text-gray-500">{sinistres.length} sinistres</span>
            </div>

            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">N°</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Immatriculation</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Montant</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {sinistres.slice(0, 50).map((s) => (
                    <tr key={s.index} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-medium text-gray-900">{s.NUM_SINISTRE || s.index}</td>
                      <td className="px-6 py-4 font-mono text-sm">{s.IMMATRICULATION}</td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {s.DATE_SURVENANCE?.split(' ')[0]}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {s.TOTALREGLEMENT ? `${s.TOTALREGLEMENT.toFixed(0)} TND` : '-'}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => analyzeSinistre(s.index)}
                          className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200"
                        >
                          Analyser
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {view === 'detail' && selectedSinistre && (
          <div className="space-y-6">
            <button
              onClick={() => setView('sinistres')}
              className="text-gray-600 hover:text-gray-900 flex items-center"
            >
              ← Retour aux sinistres
            </button>

            {/* Score Principal */}
            <div className={`card ${selectedSinistre.statut_fraude === 'frauduleux' ? 'border-4 border-red-300' : ''}`}>
              <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="text-center">
                  <div className={`text-6xl font-bold ${getScoreColor(selectedSinistre.score_suspicion)}`}>
                    {selectedSinistre.score_suspicion.toFixed(0)}
                    <span className="text-2xl">/100</span>
                  </div>
                  <p className="text-gray-500 mt-2">Score de Suspicion</p>
                </div>
                <div className="h-px md:h-24 w-full md:w-px bg-gray-300"></div>
                <div className="text-center">
                  <span className={`px-6 py-3 rounded-lg text-lg font-bold ${getStatutBadge(selectedSinistre.statut_fraude)}`}>
                    {selectedSinistre.statut_fraude === 'non_frauduleux' ? 'Non Frauduleux' :
                     selectedSinistre.statut_fraude === 'suspect' ? 'Suspect' : 'Frauduleux'}
                  </span>
                  <p className="text-gray-500 mt-2">Niveau: {selectedSinistre.niveau_risque}</p>
                </div>
              </div>
            </div>

            {/* Explication */}
            <div className="card">
              <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                <Brain className="h-5 w-5 mr-2 text-purple-600" />
                Explication Automatique
              </h3>
              <div className="bg-blue-50 rounded-lg p-4">
                <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                  {selectedSinistre.explication}
                </pre>
              </div>
            </div>

            {/* Features Anormales */}
            {selectedSinistre.features_anormales?.length > 0 && (
              <div className="card">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                  <AlertTriangle className="h-5 w-5 mr-2 text-orange-500" />
                  Caractéristiques Anormales Détectées
                </h3>
                <div className="space-y-3">
                  {selectedSinistre.features_anormales.map((f, i) => (
                    <div key={i} className="p-4 bg-orange-50 rounded-lg border border-orange-200">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-orange-900">{f.feature.replace('_', ' ').toUpperCase()}</span>
                        <span className="text-sm text-orange-700">Z-score: {f.z_score.toFixed(2)}</span>
                      </div>
                      <p className="text-sm text-orange-700 mt-1">
                        Valeur: {f.valeur.toFixed(2)} | Moyenne: {f.moyenne_dataset.toFixed(2)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default App

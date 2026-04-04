import { useEffect, useRef, useState } from 'react'
import './LocationPicker.css'

const DEFAULT_CENTER = {
  lat: 12.9716,
  lng: 77.5946,
}

const GOOGLE_SCRIPT_ID = 'covrly-google-maps-script'

const toCoordinate = (value) => {
  if (!value || typeof value !== 'object') {
    return null
  }

  const lat = Number(value.lat)
  const lng = Number(value.lng)

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null
  }

  return { lat, lng }
}

const loadGoogleMapsScript = (apiKey) =>
  new Promise((resolve, reject) => {
    if (!apiKey) {
      reject(new Error('Google Maps API key not configured.'))
      return
    }

    if (window.google?.maps?.places) {
      resolve(window.google)
      return
    }

    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID)
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(window.google))
      existingScript.addEventListener('error', () => reject(new Error('Failed to load Google Maps script.')))
      return
    }

    const script = document.createElement('script')
    script.id = GOOGLE_SCRIPT_ID
    script.async = true
    script.defer = true
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places`
    script.onload = () => resolve(window.google)
    script.onerror = () => reject(new Error('Failed to load Google Maps script.'))

    document.head.appendChild(script)
  })

function LocationPicker({ value, onChange }) {
  const mapRef = useRef(null)
  const markerRef = useRef(null)
  const autocompleteRef = useRef(null)
  const mapContainerRef = useRef(null)
  const searchInputRef = useRef(null)
  const selectedLocationRef = useRef(toCoordinate(value))
  const valueRef = useRef(value)

  const [center, setCenter] = useState(DEFAULT_CENTER)
  const [selectedLocation, setSelectedLocation] = useState(toCoordinate(value))
  const [mapLoading, setMapLoading] = useState(true)
  const [mapError, setMapError] = useState('')

  const mapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY

  useEffect(() => {
    valueRef.current = value

    const normalizedValue = toCoordinate(value)
    if (!normalizedValue) {
      return
    }

    selectedLocationRef.current = normalizedValue
    setSelectedLocation(normalizedValue)
  }, [value])

  useEffect(() => {
    selectedLocationRef.current = selectedLocation
  }, [selectedLocation])

  useEffect(() => {
    if (!navigator.geolocation) {
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCenter({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        })
      },
      () => {
        // Keep default center if geolocation fails.
      },
      {
        enableHighAccuracy: true,
        timeout: 8000,
      },
    )
  }, [])

  useEffect(() => {
    let isDisposed = false

    const updateSelection = (coordinates) => {
      if (!coordinates || isDisposed) {
        return
      }

      selectedLocationRef.current = coordinates
      setSelectedLocation(coordinates)

      if (mapRef.current) {
        mapRef.current.panTo(coordinates)
      }

      if (!markerRef.current && mapRef.current && window.google?.maps) {
        markerRef.current = new window.google.maps.Marker({
          map: mapRef.current,
          position: coordinates,
        })
      }

      if (markerRef.current) {
        markerRef.current.setPosition(coordinates)
      }

      if (typeof onChange === 'function') {
        onChange(coordinates)
      }
    }

    const initializeMap = async () => {
      setMapLoading(true)
      setMapError('')

      try {
        await loadGoogleMapsScript(mapsApiKey)
        if (isDisposed || !mapContainerRef.current || !window.google?.maps) {
          return
        }

        const initialCenter =
          toCoordinate(valueRef.current) || selectedLocationRef.current || center
        mapRef.current = new window.google.maps.Map(mapContainerRef.current, {
          center: initialCenter,
          zoom: 16,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
        })

        mapRef.current.addListener('click', (event) => {
          const lat = event.latLng?.lat()
          const lng = event.latLng?.lng()

          if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
            return
          }

          updateSelection({ lat, lng })
        })

        if (searchInputRef.current && window.google?.maps?.places) {
          autocompleteRef.current = new window.google.maps.places.Autocomplete(searchInputRef.current, {
            fields: ['geometry', 'formatted_address', 'name'],
          })

          autocompleteRef.current.addListener('place_changed', () => {
            const place = autocompleteRef.current?.getPlace()
            const placeLat = place?.geometry?.location?.lat?.()
            const placeLng = place?.geometry?.location?.lng?.()

            if (!Number.isFinite(placeLat) || !Number.isFinite(placeLng)) {
              return
            }

            updateSelection({ lat: placeLat, lng: placeLng })
          })
        }

        if (selectedLocationRef.current) {
          updateSelection(selectedLocationRef.current)
        }
      } catch (error) {
        if (!isDisposed) {
          setMapError(error instanceof Error ? error.message : 'Unable to load map.')
        }
      } finally {
        if (!isDisposed) {
          setMapLoading(false)
        }
      }
    }

    initializeMap()

    return () => {
      isDisposed = true

      if (autocompleteRef.current && window.google?.maps?.event) {
        window.google.maps.event.clearInstanceListeners(autocompleteRef.current)
      }

      if (markerRef.current) {
        markerRef.current.setMap(null)
        markerRef.current = null
      }

      if (mapRef.current && window.google?.maps?.event) {
        window.google.maps.event.clearInstanceListeners(mapRef.current)
      }

      mapRef.current = null
    }
  }, [center, mapsApiKey, onChange])

  return (
    <section className="location-picker">
      <label className="location-picker-label" htmlFor="location-search-input">
        Search location
      </label>
      <input
        id="location-search-input"
        ref={searchInputRef}
        type="text"
        className="location-picker-search"
        placeholder="Search by place, area, or address"
      />

      {mapLoading ? <p className="location-picker-status">Loading map...</p> : null}
      {mapError ? <p className="location-picker-error">{mapError}</p> : null}

      <div ref={mapContainerRef} className="location-picker-map" role="application" aria-label="Location picker map" />

      {selectedLocation ? (
        <p className="location-picker-coordinates">
          Selected: {selectedLocation.lat.toFixed(6)}, {selectedLocation.lng.toFixed(6)}
        </p>
      ) : (
        <p className="location-picker-status">Click on map or search to pick location.</p>
      )}
    </section>
  )
}

export default LocationPicker

export function buildChartData(observations) {
  return [...observations]
    .sort((a, b) => (a.observation_epoch || '').localeCompare(b.observation_epoch || ''))
    .map(obs => ({
      epoch: obs.observation_epoch,
      health: obs.derived_health_score,
      roll: obs.attitude?.roll_deg,
      pitch: obs.attitude?.pitch_deg,
      yaw: obs.attitude?.yaw_deg,
      stability: obs.attitude?.stability_flag,
      isUnstable: obs.attitude?.stability_flag != null ? obs.attitude.stability_flag !== 'nominal' : null,
      temp: obs.surface_temp_K ?? obs.thermal?.surface_temp_K,
      tempVariance: obs.surface_temp_variance_30d ?? obs.thermal?.temp_variance_30d,
      thermalAnomaly: obs.thermal?.anomaly_flag,
      reflectivity: obs.material_signature?.reflectivity_index,
      materialConfidence: obs.material_signature?.material_confidence,
      range: obs.proximity_state?.range_km,
      velocity: obs.proximity_state?.relative_velocity_ms,
      deltaV: obs.maneuver_indicator?.delta_v_residual_ms,
      manConf: obs.maneuver_indicator?.maneuver_confidence,
      manFlag: (() => {
        const raw = obs.maneuver_indicator?.maneuver_flag
        const v = (obs.maneuver_flag != null) ? obs.maneuver_flag : raw
        if (v == null) return null
        return v !== false && v !== 'false'
      })(),
      drift: obs.orbital_decay_indicator?.perigee_drift_km_per_day,
      estimatedPerigee: obs.orbital_decay_indicator?.estimated_perigee_km,
      mass: obs.estimated_mass_kg,
      spin: obs.spin_rate_rpm,
      passId: obs.pass_id,
      frameIndex: obs.frame_index,
      observationMode: obs.observation_mode,
      sensorsActive: obs.sensors_active,
      illumination: obs.illumination,
    }))
}

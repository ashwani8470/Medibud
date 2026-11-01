package com.medibud.service;

import org.springframework.stereotype.Service;

/** Earth-distance helper. We skip PostGIS and compute km in Java. */
@Service
public class DistanceService {

	private static final double EARTH_KM = 6371.0;

	public double km(double lat1, double lng1, double lat2, double lng2) {
		double dLat = Math.toRadians(lat2 - lat1);
		double dLng = Math.toRadians(lng2 - lng1);
		double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
				+ Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
						* Math.sin(dLng / 2) * Math.sin(dLng / 2);
		return 2 * EARTH_KM * Math.asin(Math.sqrt(a));
	}

	/** Rough road-time used on the list cards (same formula as the HTML demo). */
	public int etaMinutes(double km) {
		return Math.max(2, (int) Math.round(km * 2.5));
	}
}

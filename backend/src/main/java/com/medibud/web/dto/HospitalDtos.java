package com.medibud.web.dto;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/** JSON shapes returned to the patient UI. */
public final class HospitalDtos {

	private HospitalDtos() {
	}

	public record BedCount(int free, int total) {
	}

	public record DoctorView(Long id, String name, String specialty, String status, String nextFreeSlot) {
	}

	public record HospitalSummary(
			Long id,
			String name,
			double lat,
			double lng,
			String phone,
			String address,
			double distanceKm,
			int etaMinutes,
			Instant updatedAt,
			boolean demo,
			Map<String, BedCount> beds) {
	}

	public record HospitalDetail(
			Long id,
			String name,
			double lat,
			double lng,
			String phone,
			String address,
			double distanceKm,
			int etaMinutes,
			Instant updatedAt,
			boolean demo,
			List<String> facilities,
			List<String> departments,
			Map<String, BedCount> beds,
			List<DoctorView> doctors) {
	}
}

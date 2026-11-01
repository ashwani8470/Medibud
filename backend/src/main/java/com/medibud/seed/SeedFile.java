package com.medibud.seed;

import java.util.List;
import java.util.Map;

/** Mirrors seed-hospitals.json. Delete that JSON to drop dummy data. */
public class SeedFile {

	public List<HospitalSeed> hospitals;
	public List<UserSeed> users;

	public static class HospitalSeed {
		public String name;
		public double lat;
		public double lng;
		public String phone;
		public String address;
		public List<String> facilities;
		public Map<String, BedSeed> beds;
		public List<DoctorSeed> doctors;
	}

	public static class BedSeed {
		public int free;
		public int total;
	}

	public static class DoctorSeed {
		public String name;
		public String specialty;
		public String status;
		public String nextFreeSlot;
	}

	public static class UserSeed {
		public String email;
		public String password;
		public String name;
		public String role;
		public String hospitalName;
	}
}

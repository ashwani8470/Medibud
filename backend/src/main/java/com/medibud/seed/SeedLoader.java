package com.medibud.seed;

import java.io.InputStream;
import java.time.Instant;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.medibud.config.AppProperties;
import com.medibud.domain.AppUser;
import com.medibud.domain.BedInventory;
import com.medibud.domain.BedType;
import com.medibud.domain.Doctor;
import com.medibud.domain.DoctorStatus;
import com.medibud.domain.Hospital;
import com.medibud.domain.UserRole;
import com.medibud.repo.HospitalRepository;
import com.medibud.repo.UserRepository;
import com.medibud.seed.SeedFile.BedSeed;
import com.medibud.seed.SeedFile.DoctorSeed;
import com.medibud.seed.SeedFile.HospitalSeed;
import com.medibud.seed.SeedFile.UserSeed;

/**
 * Loads classpath:/data/seed-hospitals.json when DATA_MODE=dummy and the DB is empty.
 * To wipe dummy rows later: DELETE FROM ... WHERE is_demo = true
 */
@Component
public class SeedLoader implements ApplicationRunner {

	private static final Logger log = LoggerFactory.getLogger(SeedLoader.class);

	private final AppProperties props;
	private final HospitalRepository hospitals;
	private final UserRepository users;
	private final ObjectMapper mapper;

	public SeedLoader(
			AppProperties props,
			HospitalRepository hospitals,
			UserRepository users,
			ObjectMapper mapper) {
		this.props = props;
		this.hospitals = hospitals;
		this.users = users;
		this.mapper = mapper;
	}

	@Override
	@Transactional
	public void run(ApplicationArguments args) throws Exception {
		if (!props.isDummy()) {
			log.info("DATA_MODE=real — skipping dummy seed");
			return;
		}
		if (hospitals.count() > 0) {
			log.info("Database already has {} hospitals — skipping seed", hospitals.count());
			return;
		}

		ClassPathResource resource = new ClassPathResource("data/seed-hospitals.json");
		try (InputStream in = resource.getInputStream()) {
			SeedFile seed = mapper.readValue(in, SeedFile.class);
			for (HospitalSeed h : seed.hospitals) {
				hospitals.save(toHospital(h));
			}
			if (seed.users != null) {
				for (UserSeed u : seed.users) {
					users.save(toUser(u));
				}
			}
			log.info("Seeded {} demo hospitals from seed-hospitals.json", seed.hospitals.size());
		}
	}

	private Hospital toHospital(HospitalSeed src) {
		Hospital h = new Hospital();
		h.setName(src.name);
		h.setLat(src.lat);
		h.setLng(src.lng);
		h.setPhone(src.phone);
		h.setAddress(src.address);
		h.setDemo(true);
		h.setUpdatedAt(Instant.now());
		h.setFacilities(src.facilities == null ? List.of() : src.facilities);
		if (src.beds != null) {
			for (Map.Entry<String, BedSeed> e : src.beds.entrySet()) {
				BedInventory bed = new BedInventory();
				bed.setBedType(BedType.valueOf(e.getKey()));
				bed.setTotal(e.getValue().total);
				bed.setFree(Math.min(e.getValue().free, e.getValue().total));
				h.addBed(bed);
			}
		}
		if (src.doctors != null) {
			for (DoctorSeed d : src.doctors) {
				Doctor doctor = new Doctor();
				doctor.setName(d.name);
				doctor.setSpecialty(d.specialty);
				doctor.setStatus(DoctorStatus.valueOf(d.status));
				doctor.setNextFreeSlot(d.nextFreeSlot);
				doctor.setDemo(true);
				h.addDoctor(doctor);
			}
		}
		return h;
	}

	private AppUser toUser(UserSeed src) {
		AppUser user = new AppUser();
		user.setEmail(src.email);
		user.setPassword(src.password);
		user.setName(src.name);
		user.setRole(UserRole.valueOf(src.role));
		user.setDemo(true);
		if (src.hospitalName != null && !src.hospitalName.isBlank()) {
			hospitals.findAll().stream()
					.filter(h -> h.getName().equalsIgnoreCase(src.hospitalName))
					.findFirst()
					.ifPresent(user::setHospital);
		}
		return user;
	}
}

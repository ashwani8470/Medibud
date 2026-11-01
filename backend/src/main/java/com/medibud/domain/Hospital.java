package com.medibud.domain;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import jakarta.persistence.CascadeType;
import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;

/**
 * One hospital on the map. is_demo=true means it came from seed JSON
 * and can be deleted in one SQL when a real hospital onboards.
 */
@Entity
@Table(name = "hospitals")
public class Hospital {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(nullable = false)
	private String name;

	private double lat;
	private double lng;
	private String phone;
	private String address;

	@Column(name = "is_demo", nullable = false)
	private boolean demo;

	@Column(name = "updated_at", nullable = false)
	private Instant updatedAt = Instant.now();

	@ElementCollection(fetch = FetchType.EAGER)
	@CollectionTable(name = "facilities", joinColumns = @JoinColumn(name = "hospital_id"))
	@Column(name = "name")
	private List<String> facilities = new ArrayList<>();

	@OneToMany(mappedBy = "hospital", cascade = CascadeType.ALL, orphanRemoval = true)
	private List<BedInventory> beds = new ArrayList<>();

	@OneToMany(mappedBy = "hospital", cascade = CascadeType.ALL, orphanRemoval = true)
	private List<Doctor> doctors = new ArrayList<>();

	public void addBed(BedInventory bed) {
		bed.setHospital(this);
		beds.add(bed);
	}

	public void addDoctor(Doctor doctor) {
		doctor.setHospital(this);
		doctors.add(doctor);
	}

	public Long getId() {
		return id;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public double getLat() {
		return lat;
	}

	public void setLat(double lat) {
		this.lat = lat;
	}

	public double getLng() {
		return lng;
	}

	public void setLng(double lng) {
		this.lng = lng;
	}

	public String getPhone() {
		return phone;
	}

	public void setPhone(String phone) {
		this.phone = phone;
	}

	public String getAddress() {
		return address;
	}

	public void setAddress(String address) {
		this.address = address;
	}

	public boolean isDemo() {
		return demo;
	}

	public void setDemo(boolean demo) {
		this.demo = demo;
	}

	public Instant getUpdatedAt() {
		return updatedAt;
	}

	public void setUpdatedAt(Instant updatedAt) {
		this.updatedAt = updatedAt;
	}

	public List<String> getFacilities() {
		return facilities;
	}

	public void setFacilities(List<String> facilities) {
		this.facilities = facilities;
	}

	public List<BedInventory> getBeds() {
		return beds;
	}

	public List<Doctor> getDoctors() {
		return doctors;
	}
}

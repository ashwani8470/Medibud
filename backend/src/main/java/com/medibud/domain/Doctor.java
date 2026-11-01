package com.medibud.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "doctors")
public class Doctor {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "hospital_id")
	private Hospital hospital;

	@Column(nullable = false)
	private String name;

	@Column(nullable = false)
	private String specialty;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false)
	private DoctorStatus status = DoctorStatus.AVAILABLE;

	@Column(name = "next_free_slot")
	private String nextFreeSlot;

	@Column(name = "is_demo", nullable = false)
	private boolean demo = true;

	public Long getId() {
		return id;
	}

	public Hospital getHospital() {
		return hospital;
	}

	public void setHospital(Hospital hospital) {
		this.hospital = hospital;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public String getSpecialty() {
		return specialty;
	}

	public void setSpecialty(String specialty) {
		this.specialty = specialty;
	}

	public DoctorStatus getStatus() {
		return status;
	}

	public void setStatus(DoctorStatus status) {
		this.status = status;
	}

	public String getNextFreeSlot() {
		return nextFreeSlot;
	}

	public void setNextFreeSlot(String nextFreeSlot) {
		this.nextFreeSlot = nextFreeSlot;
	}

	public boolean isDemo() {
		return demo;
	}

	public void setDemo(boolean demo) {
		this.demo = demo;
	}
}

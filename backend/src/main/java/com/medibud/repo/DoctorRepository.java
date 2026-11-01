package com.medibud.repo;

import org.springframework.data.jpa.repository.JpaRepository;

import com.medibud.domain.Doctor;

public interface DoctorRepository extends JpaRepository<Doctor, Long> {
}

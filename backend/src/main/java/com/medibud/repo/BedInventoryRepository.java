package com.medibud.repo;

import org.springframework.data.jpa.repository.JpaRepository;

import com.medibud.domain.BedInventory;

public interface BedInventoryRepository extends JpaRepository<BedInventory, Long> {
}

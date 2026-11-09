//
//  MenuBarPlatformSupportTests.swift
//  FireLogicTests
//

import XCTest
@testable import FireLogic

final class MenuBarPlatformSupportTests: XCTestCase {
    func testMacOS26IsSupported() {
        XCTAssertTrue(MenuBarPlatformSupport.isItemDiscoverySupported(osMajorVersion: 26, hasModernBackend: false))
    }

    func testOlderMacOSIsSupported() {
        XCTAssertTrue(MenuBarPlatformSupport.isItemDiscoverySupported(osMajorVersion: 14, hasModernBackend: false))
    }

    func testMacOS27WithoutBackendIsUnsupported() {
        XCTAssertFalse(MenuBarPlatformSupport.isItemDiscoverySupported(osMajorVersion: 27, hasModernBackend: false))
    }

    func testLaterMacOSWithoutBackendIsUnsupported() {
        XCTAssertFalse(MenuBarPlatformSupport.isItemDiscoverySupported(osMajorVersion: 28, hasModernBackend: false))
    }

    func testMacOS27WithBackendIsSupported() {
        XCTAssertTrue(MenuBarPlatformSupport.isItemDiscoverySupported(osMajorVersion: 27, hasModernBackend: true))
    }

    func testModernBackendIsStillDisabled() {
        // Flip this expectation when the macOS 27 backend lands (issue #25).
        XCTAssertFalse(MenuBarPlatformSupport.hasModernBackend)
    }
}

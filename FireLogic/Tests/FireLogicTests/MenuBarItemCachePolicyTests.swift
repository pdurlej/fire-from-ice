//
//  MenuBarItemCachePolicyTests.swift
//  FireLogicTests
//

import XCTest
@testable import FireLogic

final class MenuBarItemCachePolicyTests: XCTestCase {
    func testMissingControlItemCanRecoverWithoutWindowIDsChanging() {
        let windowIDs: [UInt32] = [11, 22, 33]

        // Discovery records these IDs, but a nil source PID prevents the
        // hidden divider from matching its tag and leaves the item cache empty.
        XCTAssertTrue(MenuBarItemCachePolicy.shouldRefresh(
            cachedWindowIDs: windowIDs,
            currentWindowIDs: windowIDs,
            hasManagedItems: false
        ))

        // The next discovery can resolve that same divider window. Once the
        // cache has items, unchanged IDs should again skip expensive AX work.
        XCTAssertFalse(MenuBarItemCachePolicy.shouldRefresh(
            cachedWindowIDs: windowIDs,
            currentWindowIDs: windowIDs,
            hasManagedItems: true
        ))
    }

    func testChangedWindowIDsRefreshPopulatedCache() {
        XCTAssertTrue(MenuBarItemCachePolicy.shouldRefresh(
            cachedWindowIDs: [11, 22],
            currentWindowIDs: [11, 33],
            hasManagedItems: true
        ))
    }

    func testChangedOrderingRefreshesPopulatedCache() {
        XCTAssertTrue(MenuBarItemCachePolicy.shouldRefresh(
            cachedWindowIDs: [11, 22],
            currentWindowIDs: [22, 11],
            hasManagedItems: true
        ))
    }

    func testEmptyDiscoveryDoesNotSuppressLaterAttempts() {
        XCTAssertTrue(MenuBarItemCachePolicy.shouldRefresh(
            cachedWindowIDs: [],
            currentWindowIDs: [],
            hasManagedItems: false
        ))
    }
}

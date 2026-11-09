//
//  MenuBarPlatformSupport.swift
//  Ice
//

import Foundation

/// Decides whether Fire can discover (and therefore display and arrange)
/// individual menu bar items on the running macOS.
///
/// macOS 27 draws the whole menu bar as a single window, so the per-item
/// window enumeration inherited from Ice finds nothing there and the item
/// cache stays empty forever (issue #25). Until a macOS 27 backend lands,
/// views that would otherwise spin on "Loading menu bar items…" show an
/// honest "not supported yet" notice instead (issue #32).
///
/// To remove the notice once the macOS 27 backend ships, make
/// ``hasModernBackend`` return `true` when that backend is active. The views
/// only consult ``isItemDiscoverySupportedOnCurrentSystem``.
enum MenuBarPlatformSupport {
    /// The first macOS major version that no longer exposes one window per
    /// menu bar item.
    static let firstSingleWindowMenuBarMajorVersion = 27

    /// Whether a backend that can discover items on macOS 27+ is available.
    ///
    /// Hard-coded to `false` until the macOS 27 hiding work lands.
    static let hasModernBackend = false

    /// Pure decision function, kept free of system state so it can be unit
    /// tested in `FireLogic`.
    static func isItemDiscoverySupported(osMajorVersion: Int, hasModernBackend: Bool) -> Bool {
        osMajorVersion < firstSingleWindowMenuBarMajorVersion || hasModernBackend
    }

    /// The decision for the running system.
    static let isItemDiscoverySupportedOnCurrentSystem = isItemDiscoverySupported(
        osMajorVersion: ProcessInfo.processInfo.operatingSystemVersion.majorVersion,
        hasModernBackend: hasModernBackend
    )
}

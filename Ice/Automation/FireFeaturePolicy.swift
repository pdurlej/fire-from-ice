//
//  FireFeaturePolicy.swift
//  Ice
//

import Foundation

/// Pure policy for keeping Fire's menu bar foundation independent from its
/// optional experimental features (AI quotas, the MCP server, automations).
///
/// All of them sit behind one user-visible switch, Settings > Advanced >
/// Experimental. It is persisted under the `ContextsAndAgentsEnabled` key
/// (shared with MCPBackend.xpc and the MCP bridge), so a stored choice from
/// the earlier "Contexts & Agents" toggle carries over unchanged.
struct FireFeaturePolicy: Equatable {
    struct InitialOptionalFeatureState: Equatable {
        let experimentalFeaturesEnabled: Bool
        let mcpServerEnabled: Bool
        let mcpAllowWrites: Bool
    }

    /// Resolves the first rebuild state for optional features.
    ///
    /// - A stored top-level choice always wins, and nested configuration is
    ///   preserved as-is (its runtime is simply paused while the switch is off).
    /// - With no stored choice (upgrade from a build before the switch), the
    ///   switch turns on only when there is evidence the user actually used an
    ///   experimental feature: AI quotas enabled, stored automations, or an MCP
    ///   setup the fire.10.4 migration could not have produced.
    /// - The fire.10.4 migration seeded `MCPServerEnabled = true` and
    ///   `MCPAllowWrites = true` for every upgrade, so that pair cannot prove
    ///   intent and is reset. Server on with writes off is not something that
    ///   migration writes, so it is a deliberate read-only setup and is kept.
    static func initialOptionalFeatureState(
        storedExperimentalFeaturesEnabled: Bool?,
        storedMCPServerEnabled: Bool?,
        storedMCPAllowWrites: Bool?,
        legacyAIQuotasEnabled: Bool,
        hasStoredTriggers: Bool
    ) -> InitialOptionalFeatureState {
        if let storedExperimentalFeaturesEnabled {
            return InitialOptionalFeatureState(
                experimentalFeaturesEnabled: storedExperimentalFeaturesEnabled,
                mcpServerEnabled: storedMCPServerEnabled ?? false,
                mcpAllowWrites: storedMCPAllowWrites ?? false
            )
        }

        let deliberateReadOnlyMCP = storedMCPServerEnabled == true && storedMCPAllowWrites == false

        return InitialOptionalFeatureState(
            experimentalFeaturesEnabled: legacyAIQuotasEnabled || hasStoredTriggers || deliberateReadOnlyMCP,
            mcpServerEnabled: deliberateReadOnlyMCP,
            mcpAllowWrites: false
        )
    }

    /// Whether a Settings pane that exists only for experimental features
    /// (today: Automations) is shown in the sidebar.
    static func isExperimentalPaneVisible(experimentalFeaturesEnabled: Bool) -> Bool {
        experimentalFeaturesEnabled
    }
}

/// A stopped trigger runtime may reload persisted rules for its settings UI,
/// but it must never evaluate or fire them until the user opts back in.
enum TriggerRuntimePolicy {
    static func shouldEvaluate(isRunning: Bool) -> Bool {
        isRunning
    }
}

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { CollaborationController } from "./collaboration.controller";
import { DocumentController } from "./document.controller";
import { HealthController } from "./health.controller";
import { PdfExportController } from "./pdf-export.controller";
import { OcesEventsController } from "@/oces/events.controller"; // OCES: live updates
import { OcesPageContentController } from "@/oces/page-content"; // OCES: pages public API

export const CONTROLLERS = [
  CollaborationController,
  DocumentController,
  HealthController,
  PdfExportController,
  OcesEventsController, // OCES: live updates
  OcesPageContentController, // OCES: pages public API
];

package com.learnassist.api.web;

import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.DashboardService;
import java.time.DateTimeException;
import java.time.ZoneId;
import java.time.ZoneOffset;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DashboardController {

    private final DashboardService dashboard;

    public DashboardController(DashboardService dashboard) {
        this.dashboard = dashboard;
    }

    /**
     * @param tz the browser's IANA time zone, e.g. {@code Asia/Phnom_Penh}; days are bucketed in
     *           it. Unknown values fall back to UTC rather than failing the whole dashboard.
     */
    @GetMapping("/api/dashboard")
    public DashboardService.Dashboard get(@RequestParam(defaultValue = "UTC") String tz) {
        ZoneId zone;
        try {
            zone = ZoneId.of(tz);
        } catch (DateTimeException e) {
            zone = ZoneOffset.UTC;
        }
        return dashboard.build(CurrentUser.require(), zone);
    }
}

import React from "react";
import { PowerBIEmbed } from "powerbi-client-react";
import { models } from "powerbi-client";
import "./App.css";

const PowerBIReport = () => {
  return (
    <div id="reportContainer" className="report-container">
      <PowerBIEmbed
        embedConfig={{
          type: "report",
          id: "9ef9afa4-9521-494d-bd9a-eaf113935369",
          embedUrl:
            "https://app.powerbi.com/view?r=eyJrIjoiZmU4ZTU5ODktZDcxZS00YWUyLWE0YWUtMDIyMjdiNjY3Y2Y0IiwidCI6ImZjMDA1NDdhLTI0YmItNGU0Zi05ZDYxLTczZmNhNWViOWRmMyIsImMiOjR9",
          tokenType: models.TokenType.Embed,
          settings: {
            panes: {
              filters: { visible: false },
              pageNavigation: { visible: false },
            },
          },
        }}
        getEmbeddedComponent={async (embeddedReport) => {
          window.report = embeddedReport;
          console.log("Report has been embedded:", embeddedReport);

          await embeddedReport.getPages().then((pages) => {
            pages.forEach((page) => console.log(page.name));
          });
        }}
      />
    </div>
  );
};

export default PowerBIReport;

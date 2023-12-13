/**
 * helper to wait for an element to be available in the DOM.
 * 
 * @param {*} selector 
 * @returns 
 */
function waitForElm(selector) {
    parent.window.console.log("waitForElm(" + selector + ")")
    return new Promise(resolve => {
        if (parent.window.document.querySelector(selector)) {
            return resolve(window.document.querySelector(selector));
        }

        const observer = new MutationObserver(mutations => {
            if (parent.window.document.querySelector(selector)) {
                resolve(parent.window.document.querySelector(selector));
                observer.disconnect();
            }
        });

        observer.observe(parent.window.document.body, {
            childList: true,
            subtree: true
        });
    });
}

/**
 * replace the Streamlit menu by a link to the WSE website.
 */
waitForElm('#MainMenu').then((elm) => {
    parent.window.console.log('Element is ready');
    if (parent.window.document.getElementById("WSElogo") == null) {
        let new_logo = parent.window.document.getElementById("MainMenu").parentElement.appendChild(parent.window.document.createElement("span"));
        new_logo.innerHTML = `
        <a href="https://wse-research.org?utm_source=knowledge_graph_visualizer" title="Brought to you by the WSE research group at the Leipzig University of Applied Sciences. See our GitHub team page for more projects and tools." target="_blank">
        <img id="WSElogo" src='https://avatars.githubusercontent.com/u/120292474?s=96&v=4'>
        </a>
        <style>
        </style>
        `;
    }

    // for all iframes 
    let iframes = parent.window.document.getElementsByTagName("iframe");

    // styles for iframes
    let styles = {
        ["0"]: {
            inner_style: `
                span.rti--tag {
                    background-color: #FFF !important;
                }
                span.rti--tag span {
                    color: #000000 !important;
                }
                span.rti--tag button {
                    color: #000000;
                }
                `,
            outer_style: `
                margin-top: -3ex !important;
            `
        },
        ["1"]: {
            inner_style: `
                span.rti--tag {
                    background-color: #000 !important;
                }
                span.rti--tag span {
                    color: #FFF !important;
                }
                `,
            outer_style: `
                margin-top: -3ex !important;
            `
        },
        ["2"]: {
            inner_style: `
                span.rti--tag {
                    background-color: #00F !important;
                }
                span.rti--tag span {
                    color: #FFF !important;
                }
                `,
            outer_style: `
                margin-top: -3ex !important;
            `
        }
    }

    // apply styles to iframes
    for (let i = 0; i < iframes.length; i++) {
        let iframe = iframes[i];
        let style = parent.window.document.createElement("style");
        if (styles[i] == undefined) {
            continue;
        } else {
            style.innerHTML = styles[i].inner_style;
            iframe.contentDocument.head.appendChild(style);
            console.log("added style tag to iframe " + i);
            iframe.style = styles[i].outer_style;
        }
    }

});